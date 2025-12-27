#!/usr/bin/env python3
import warnings
warnings.filterwarnings('ignore', message='urllib3 v2 only supports OpenSSL')

import click
import yaml
import json
from pathlib import Path
from rich.console import Console
from rich.table import Table
from rich.prompt import Prompt
from rich import print as rprint
from vezor import VezorClient as VezorAPIClient
from config import CLIConfig
from supabase_client import SupabaseAuthClient

console = Console()


def get_client() -> VezorAPIClient:
    """Get authenticated API client with organization context"""
    token = CLIConfig.get_token()
    api_url = CLIConfig.get_api_url()
    org_id = CLIConfig.get_organization_id()

    if not token:
        console.print("[red]Error: Not authenticated. Run 'vezor login' first.[/red]")
        raise click.Abort()

    if not org_id:
        console.print("[red]Error: No organization selected. Run 'vezor orgs' to select one.[/red]")
        raise click.Abort()

    return VezorAPIClient(api_url, token, org_id)


def get_client_no_org() -> VezorAPIClient:
    """Get authenticated API client without requiring organization"""
    token = CLIConfig.get_token()
    api_url = CLIConfig.get_api_url()

    if not token:
        console.print("[red]Error: Not authenticated. Run 'vezor login' first.[/red]")
        raise click.Abort()

    return VezorAPIClient(api_url, token)


def parse_tags(tag_strings: tuple) -> dict:
    """Parse tag strings like 'env=prod' into dict"""
    tags = {}
    for tag_str in tag_strings:
        if '=' in tag_str:
            key, value = tag_str.split('=', 1)
            tags[key.strip()] = value.strip()
    return tags


@click.group()
@click.version_option(version='2.0.0')
def cli():
    """Vezor - GitOps-native secrets management"""
    pass


# ============ Auth Commands ============

@cli.command()
def login():
    """Authenticate with Vezor"""
    supabase_url = CLIConfig.get_supabase_url()
    supabase_key = CLIConfig.get_supabase_anon_key()

    console.print(f"[cyan]Signing in to Vezor...[/cyan]")

    email = Prompt.ask("Email")
    password = Prompt.ask("Password", password=True)

    try:
        supabase_client = SupabaseAuthClient(supabase_url, supabase_key)
        result = supabase_client.sign_in(email, password)

        access_token = result['session']['access_token']
        CLIConfig.set_token(access_token)

        console.print(f"[green]Signed in successfully as {email}[/green]")

        # Auto-select organization if only one
        client = VezorAPIClient(CLIConfig.get_api_url(), access_token)
        try:
            orgs_result = client.list_organizations()
            orgs = orgs_result if isinstance(orgs_result, list) else orgs_result.get('organizations', [])
            if len(orgs) == 1:
                CLIConfig.set_organization_id(orgs[0]['id'])
                CLIConfig.set_organization_name(orgs[0]['name'])
                console.print(f"[dim]Organization: {orgs[0]['name']}[/dim]")
            elif len(orgs) > 1:
                console.print(f"\n[yellow]You belong to {len(orgs)} organizations.[/yellow]")
                console.print("Run [cyan]vezor orgs[/cyan] to select one.")
            else:
                console.print("\n[yellow]No organizations found.[/yellow]")
                console.print("Run [cyan]vezor org create <name>[/cyan] to create one.")
        except Exception:
            pass

    except Exception as e:
        console.print(f"[red]Sign in failed: {str(e)}[/red]")
        raise click.Abort()


@cli.command()
def logout():
    """Remove stored credentials"""
    CLIConfig.delete_token()
    CLIConfig.clear_organization()
    console.print("[green]Logged out successfully[/green]")


@cli.command()
def whoami():
    """Show current user and organization"""
    token = CLIConfig.get_token()
    if not token:
        console.print("[yellow]Not logged in[/yellow]")
        return

    org_id = CLIConfig.get_organization_id()
    org_name = CLIConfig.get_organization_name()

    console.print("[cyan]Current session:[/cyan]")
    console.print(f"  Authenticated: [green]Yes[/green]")
    if org_name:
        console.print(f"  Organization: [green]{org_name}[/green]")
    else:
        console.print(f"  Organization: [yellow]None selected[/yellow]")


# ============ Organization Commands ============

@cli.command()
def orgs():
    """List and select organizations"""
    client = get_client_no_org()

    try:
        result = client.list_organizations()
        # API returns list directly
        orgs = result if isinstance(result, list) else result.get('organizations', [])

        if not orgs:
            console.print("[yellow]No organizations found.[/yellow]")
            console.print("Run [cyan]vezor org create <name>[/cyan] to create one.")
            return

        current_org_id = CLIConfig.get_organization_id()

        table = Table(title="Your Organizations")
        table.add_column("#", style="dim", width=3)
        table.add_column("Name", style="cyan")
        table.add_column("Role", style="yellow")
        table.add_column("Current", style="green")

        for i, org in enumerate(orgs, 1):
            is_current = ">" if org['id'] == current_org_id else ""
            table.add_row(str(i), org['name'], org.get('role', 'member'), is_current)

        console.print(table)

        # Prompt to select
        if len(orgs) > 1:
            choice = Prompt.ask(
                "\nSelect organization (number)",
                default="",
                show_default=False
            )
            if choice:
                try:
                    idx = int(choice) - 1
                    if 0 <= idx < len(orgs):
                        selected = orgs[idx]
                        CLIConfig.set_organization_id(selected['id'])
                        CLIConfig.set_organization_name(selected['name'])
                        console.print(f"[green]Switched to {selected['name']}[/green]")
                except ValueError:
                    pass
        elif len(orgs) == 1 and not current_org_id:
            CLIConfig.set_organization_id(orgs[0]['id'])
            CLIConfig.set_organization_name(orgs[0]['name'])
            console.print(f"[green]Selected {orgs[0]['name']}[/green]")

    except Exception as e:
        console.print(f"[red]Failed to list organizations: {str(e)}[/red]")
        raise click.Abort()


# ============ Secret Commands ============

@cli.command('list')
@click.option('--env', '-e', help='Filter by environment tag')
@click.option('--app', '-a', help='Filter by app tag')
@click.option('--tag', '-t', multiple=True, help='Filter by tag (key=value)')
@click.option('--search', '-s', help='Search by key name')
@click.option('--limit', '-l', default=50, help='Max results')
@click.option('--output', '-o', type=click.Choice(['text', 'csv', 'json']), default='text', help='Output format')
def list_secrets(env, app, tag, search, limit, output):
    """List secrets"""
    client = get_client()

    try:
        # Build tag filters
        tags = parse_tags(tag)
        if env:
            tags['env'] = env
        if app:
            tags['app'] = app

        result = client.list_secrets(tags=tags if tags else None, search=search, limit=limit)
        secrets = result.get('secrets', [])
        total = result.get('total', len(secrets))

        if not secrets:
            if output == 'json':
                print(json.dumps({'secrets': [], 'total': 0}))
            elif output == 'csv':
                print('key_name,env,app,version,updated_at')
            else:
                console.print("[yellow]No secrets found[/yellow]")
            return

        if output == 'json':
            print(json.dumps({'secrets': secrets, 'total': total}, indent=2))
        elif output == 'csv':
            print('key_name,env,app,version,updated_at')
            for secret in secrets:
                secret_tags = secret.get('tags') or {}
                print(f"{secret['key_name']},{secret_tags.get('env', '')},{secret_tags.get('app', '')},{secret.get('version', 1)},{secret.get('updated_at', '')[:10] if secret.get('updated_at') else ''}")
        else:
            table = Table(title=f"Secrets ({len(secrets)} of {total})")
            table.add_column("Key", style="cyan")
            table.add_column("Tags", style="yellow")
            table.add_column("Version", style="magenta")
            table.add_column("Updated", style="dim")

            for secret in secrets:
                tags_str = ", ".join(f"{k}={v}" for k, v in (secret.get('tags') or {}).items())
                table.add_row(
                    secret['key_name'],
                    tags_str[:40] + "..." if len(tags_str) > 40 else tags_str,
                    f"v{secret.get('version', 1)}",
                    secret.get('updated_at', '')[:10] if secret.get('updated_at') else ''
                )

            console.print(table)

    except Exception as e:
        console.print(f"[red]Failed to list secrets: {str(e)}[/red]")
        raise click.Abort()


@cli.command('get')
@click.argument('key_name')
@click.option('--env', '-e', help='Environment tag to filter by')
@click.option('--app', '-a', help='App tag to filter by')
@click.option('--version', '-v', type=int, help='Specific version to retrieve')
@click.option('--output', '-o', type=click.Choice(['text', 'csv', 'json', 'value']), default='text', help='Output format')
def get_secret(key_name, env, app, version, output):
    """Get a secret value"""
    client = get_client()

    try:
        # Find the secret by key_name
        tags = {}
        if env:
            tags['env'] = env
        if app:
            tags['app'] = app
        result = client.list_secrets(tags=tags if tags else None, search=key_name)
        secrets = result.get('secrets', [])

        # Find exact matches
        matches = [s for s in secrets if s['key_name'].lower() == key_name.lower()]

        if not matches:
            if output == 'json':
                print(json.dumps({'error': 'Secret not found'}))
            else:
                console.print(f"[red]Secret '{key_name}' not found[/red]")
            raise click.Abort()

        if len(matches) > 1:
            if output == 'json':
                print(json.dumps({'error': 'Multiple secrets found, specify --env or --app'}))
            else:
                console.print(f"[yellow]Multiple secrets named '{key_name}' found:[/yellow]")
                for m in matches:
                    mtags = m.get('tags') or {}
                    console.print(f"  - env={mtags.get('env', '?')}, app={mtags.get('app', '?')}")
                console.print("\n[dim]Use --env and/or --app to specify which one.[/dim]")
            raise click.Abort()

        match = matches[0]

        # Get the secret value
        try:
            secret = client.get_secret(match['id'], version=version)
        except Exception as e:
            if '404' in str(e):
                if output == 'json':
                    print(json.dumps({'error': 'Secret value not found in vault'}))
                else:
                    console.print(f"[yellow]Secret '{key_name}' exists but has no value in vault[/yellow]")
                    console.print("[dim]This secret may need to be re-saved to store its value.[/dim]")
                raise click.Abort()
            raise

        if output == 'json':
            print(json.dumps(secret, indent=2))
        elif output == 'csv':
            secret_tags = secret.get('tags') or {}
            print('key_name,value,env,app,version')
            print(f"{secret['key_name']},{secret.get('value', '')},{secret_tags.get('env', '')},{secret_tags.get('app', '')},{secret.get('version', 1)}")
        elif output == 'value':
            print(secret.get('value', ''))
        else:
            console.print(f"\n[cyan]{secret['key_name']}[/cyan]")
            if secret.get('tags'):
                tags_str = ", ".join(f"{k}={v}" for k, v in secret['tags'].items())
                console.print(f"[dim]Tags: {tags_str}[/dim]")
            console.print(f"[dim]Version: v{secret.get('version', 1)}[/dim]")
            if version:
                console.print(f"[dim](Showing version {version})[/dim]")
            console.print(f"\nValue: {secret.get('value', '[no value]')}")

    except click.Abort:
        raise
    except Exception as e:
        console.print(f"[red]Failed to get secret: {str(e)}[/red]")
        raise click.Abort()


@cli.command('set')
@click.argument('key_name')
@click.option('--env', '-e', required=True, help='Environment tag (required)')
@click.option('--app', '-a', required=True, help='App tag (required)')
@click.option('--tag', '-t', multiple=True, help='Additional tag (key=value)')
@click.option('--value', prompt=True, hide_input=True, help='Secret value')
@click.option('--description', '-d', default='', help='Secret description')
@click.option('--type', 'value_type', default='string', help='Value type')
def set_secret(key_name, env, app, tag, value, description, value_type):
    """Create or update a secret"""
    client = get_client()

    try:
        # Build tags
        tags = parse_tags(tag)
        tags['env'] = env
        tags['app'] = app

        # Check if secret exists
        result = client.list_secrets(tags={'env': env, 'app': app}, search=key_name)
        secrets = result.get('secrets', [])

        existing = None
        for s in secrets:
            if s['key_name'].lower() == key_name.lower():
                existing = s
                break

        if existing:
            # Update
            result = client.update_secret(existing['id'], value=value, description=description or None, tags=tags)
            console.print(f"[green]Updated secret: {key_name} (v{result.get('version', '?')})[/green]")
        else:
            # Create
            result = client.create_secret(
                key_name=key_name,
                value=value,
                tags=tags,
                description=description,
                value_type=value_type
            )
            console.print(f"[green]Created secret: {key_name}[/green]")

    except Exception as e:
        console.print(f"[red]Failed to set secret: {str(e)}[/red]")
        raise click.Abort()


@cli.command('delete')
@click.argument('key_name')
@click.option('--env', '-e', help='Environment tag to filter by')
@click.option('--force', '-f', is_flag=True, help='Skip confirmation')
def delete_secret(key_name, env, force):
    """Delete a secret"""
    client = get_client()

    try:
        # Find the secret
        tags = {'env': env} if env else None
        result = client.list_secrets(tags=tags, search=key_name)
        secrets = result.get('secrets', [])

        match = None
        for s in secrets:
            if s['key_name'].lower() == key_name.lower():
                match = s
                break

        if not match:
            console.print(f"[red]Secret '{key_name}' not found[/red]")
            raise click.Abort()

        # Confirm
        if not force:
            tags_str = ", ".join(f"{k}={v}" for k, v in (match.get('tags') or {}).items())
            console.print(f"Secret: [cyan]{match['key_name']}[/cyan]")
            console.print(f"Tags: {tags_str}")
            if not click.confirm("Delete this secret (all versions)?"):
                return

        client.delete_secret(match['id'])
        console.print(f"[green]Deleted secret: {key_name}[/green]")

    except click.Abort:
        raise
    except Exception as e:
        console.print(f"[red]Failed to delete secret: {str(e)}[/red]")
        raise click.Abort()


@cli.command('versions')
@click.argument('key_name')
@click.option('--env', '-e', help='Environment tag to filter by')
def show_versions(key_name, env):
    """Show version history for a secret"""
    client = get_client()

    try:
        # Find the secret
        tags = {'env': env} if env else None
        result = client.list_secrets(tags=tags, search=key_name)
        secrets = result.get('secrets', [])

        match = None
        for s in secrets:
            if s['key_name'].lower() == key_name.lower():
                match = s
                break

        if not match:
            console.print(f"[red]Secret '{key_name}' not found[/red]")
            raise click.Abort()

        # Get versions
        versions_result = client.get_secret_versions(match['id'])
        versions = versions_result.get('versions', [])

        if not versions:
            console.print("[yellow]No version history found[/yellow]")
            return

        table = Table(title=f"Version History: {key_name}")
        table.add_column("Version", style="cyan")
        table.add_column("Created", style="dim")
        table.add_column("Created By", style="yellow")
        table.add_column("Current", style="green")

        current_version = versions_result.get('current_version', 1)
        for v in versions:
            is_current = ">" if v['version'] == current_version else ""
            table.add_row(
                f"v{v['version']}",
                v.get('created_at', '')[:19] if v.get('created_at') else '',
                v.get('created_by', '-'),
                is_current
            )

        console.print(table)
        console.print(f"\n[dim]Use 'vezor get {key_name} --version N' to view a specific version[/dim]")

    except click.Abort:
        raise
    except Exception as e:
        console.print(f"[red]Failed to get versions: {str(e)}[/red]")
        raise click.Abort()


# ============ Tags Command ============

@cli.command('tags')
def show_tags():
    """Show available tags"""
    client = get_client()

    try:
        result = client.get_tags()

        table = Table(title="Available Tags")
        table.add_column("Key", style="cyan")
        table.add_column("Values", style="yellow")

        for key in ['env', 'app', 'team', 'region']:
            values = result.get(key, [])
            if values:
                table.add_row(key, ", ".join(values))

        # Custom tags
        for key, values in result.items():
            if key not in ['env', 'app', 'team', 'region'] and values:
                table.add_row(key, ", ".join(values))

        console.print(table)

    except Exception as e:
        console.print(f"[red]Failed to get tags: {str(e)}[/red]")
        raise click.Abort()


# ============ Import/Export Commands ============

@cli.command('init-schema')
def init_schema():
    """Create a vezor.schema.yml template file"""
    schema_file = Path('vezor.schema.yml')

    if schema_file.exists():
        if not click.confirm('vezor.schema.yml already exists. Overwrite?'):
            return

    example_schema = {
        'version': 1,
        'service': 'my-app',
        'base': {
            'database_url': {
                'type': 'connection_string',
                'required': True,
                'description': 'Database connection string',
            },
            'api_key': {
                'type': 'string',
                'required': True,
                'description': 'API key for external service'
            },
        },
        'environments': {
            'development': {'inherit': 'base'},
            'staging': {'inherit': 'base'},
            'production': {'inherit': 'base'}
        }
    }

    with open(schema_file, 'w') as f:
        yaml.dump(example_schema, f, default_flow_style=False, sort_keys=False)

    console.print("[green]Created vezor.schema.yml[/green]")


@cli.command()
@click.option('--environment', '-e', default='development', help='Environment to validate')
def validate(environment):
    """Validate secrets against schema"""
    client = get_client()

    schema_file = Path('vezor.schema.yml')
    if not schema_file.exists():
        console.print("[red]vezor.schema.yml not found. Run 'vezor init' first.[/red]")
        raise click.Abort()

    with open(schema_file, 'r') as f:
        schema_content = f.read()

    try:
        result = client.validate_schema(schema_content, environment)

        console.print(f"\n[cyan]Validation results for {environment}:[/cyan]\n")

        if result.get('missing'):
            console.print("[red]Missing required secrets:[/red]")
            for item in result['missing']:
                console.print(f"  {item['key']}")

        if result.get('valid_secrets'):
            console.print(f"\n[green]Valid secrets: {len(result['valid_secrets'])}[/green]")

    except Exception as e:
        console.print(f"[red]Validation failed: {str(e)}[/red]")
        raise click.Abort()


@cli.command('export')
@click.option('--env', '-e', default=None, help='Filter by env tag')
@click.option('--app', '-a', default=None, help='Filter by app tag')
@click.option('--team', '-t', default=None, help='Filter by team tag')
@click.option('--region', '-r', default=None, help='Filter by region tag')
@click.option('--output', '-o', type=click.Path(), help='Output file')
def export_env(env, app, team, region, output):
    """Export secrets as .env file (no filters = all secrets)"""
    client = get_client()

    try:
        # Build tags dict from provided filters
        tags = {}
        if env:
            tags['env'] = env
        if app:
            tags['app'] = app
        if team:
            tags['team'] = team
        if region:
            tags['region'] = region

        env_content = client.export_env(tags if tags else None)

        if not env_content.strip():
            return

        if output:
            with open(output, 'w') as f:
                f.write(env_content)
            console.print(f"[green]Exported to {output}[/green]")
        else:
            console.print(env_content)

    except Exception as e:
        console.print(f"[red]Failed to export: {str(e)}[/red]")
        raise click.Abort()


@cli.command('import')
@click.argument('file', type=click.Path(exists=True))
@click.option('--env', '-e', required=True, help='Environment to import into')
def import_env(file, env):
    """Import secrets from .env file"""
    client = get_client()

    with open(file, 'r') as f:
        env_content = f.read()

    try:
        result = client.import_env(env, env_content)
        console.print(f"[green]Imported {result.get('imported', 0)} secrets to {env}[/green]")

        if result.get('errors'):
            console.print("\n[yellow]Errors:[/yellow]")
            for error in result['errors']:
                console.print(f"  {error}")

    except Exception as e:
        console.print(f"[red]Import failed: {str(e)}[/red]")
        raise click.Abort()


# ============ Groups Commands ============

@cli.command('groups')
@click.option('--output', '-o', type=click.Choice(['text', 'json']), default='text', help='Output format')
def list_groups(output):
    """List all groups"""
    client = get_client()

    try:
        result = client.list_groups()
        groups = result.get('groups', [])

        if not groups:
            if output == 'json':
                print(json.dumps({'groups': []}))
            else:
                console.print("[yellow]No groups found[/yellow]")
                console.print("[dim]Create groups in the web UI to define saved tag queries.[/dim]")
            return

        if output == 'json':
            print(json.dumps({'groups': groups}, indent=2))
        else:
            table = Table(title=f"Groups ({len(groups)})")
            table.add_column("Name", style="cyan")
            table.add_column("Tags", style="yellow")
            table.add_column("Description", style="dim")

            for group in groups:
                tags_str = ", ".join(f"{k}={v}" for k, v in (group.get('tags') or {}).items())
                table.add_row(
                    group['name'],
                    tags_str[:50] + "..." if len(tags_str) > 50 else tags_str,
                    (group.get('description') or '')[:40]
                )

            console.print(table)
            console.print("\n[dim]Use 'vezor pull --group <name>' to fetch secrets for a group.[/dim]")

    except Exception as e:
        console.print(f"[red]Failed to list groups: {str(e)}[/red]")
        raise click.Abort()


@cli.command('pull')
@click.option('--group', '-g', required=True, help='Group name to pull secrets from')
@click.option('--format', '-f', 'output_format', type=click.Choice(['env', 'export', 'json']), default='env', help='Output format')
@click.option('--output', '-o', type=click.Path(), help='Output file (otherwise prints to stdout)')
def pull_group(group, output_format, output):
    """Pull secrets from a group"""
    client = get_client()

    try:
        # Get group info first
        group_info = client.get_group(group)
        tags_str = ", ".join(f"{k}={v}" for k, v in (group_info.get('tags') or {}).items())

        # Pull secrets
        result = client.pull_group_secrets(group, format=output_format)

        if output_format == 'json':
            content = json.dumps(result, indent=2)
            if output:
                with open(output, 'w') as f:
                    f.write(content)
                console.print(f"[green]Exported {result.get('count', 0)} secrets to {output}[/green]")
                console.print(f"[dim]Group: {group} ({tags_str})[/dim]")
            else:
                print(content)
        else:
            # env or export format - result is already a string
            content = result
            if not content.strip():
                console.print(f"[yellow]No secrets found for group '{group}'[/yellow]")
                console.print(f"[dim]Tags: {tags_str}[/dim]")
                return

            if output:
                with open(output, 'w') as f:
                    f.write(content)
                secret_count = len([l for l in content.split('\n') if l.strip() and not l.startswith('#')])
                console.print(f"[green]Exported {secret_count} secrets to {output}[/green]")
                console.print(f"[dim]Group: {group} ({tags_str})[/dim]")
            else:
                print(content)

    except Exception as e:
        if '404' in str(e):
            console.print(f"[red]Group '{group}' not found[/red]")
        else:
            console.print(f"[red]Failed to pull secrets: {str(e)}[/red]")
        raise click.Abort()


@cli.command()
@click.option('--limit', default=20, help='Number of entries')
def audit(limit):
    """View audit log"""
    client = get_client()

    try:
        result = client.get_audit_log(limit=limit)
        logs = result.get('logs', [])

        if not logs:
            console.print("[yellow]No audit log entries found[/yellow]")
            return

        table = Table(title="Audit Log")
        table.add_column("Time", style="dim")
        table.add_column("User", style="cyan")
        table.add_column("Action", style="yellow")
        table.add_column("Secret", style="green")

        for log in logs:
            table.add_row(
                log.get('timestamp', '')[:19] if log.get('timestamp') else '',
                log.get('user_email', 'N/A'),
                log.get('action', ''),
                log.get('secret_path', '-')
            )

        console.print(table)

    except Exception as e:
        console.print(f"[red]Failed to get audit log: {str(e)}[/red]")
        raise click.Abort()


if __name__ == '__main__':
    cli()
