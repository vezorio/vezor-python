from setuptools import setup, find_packages

setup(
    name='vezor',
    version='2.0.0',
    description='GitOps-native secrets management SDK and CLI',
    long_description=open('README.md').read() if __import__('os').path.exists('README.md') else '',
    long_description_content_type='text/markdown',
    author='Vezor Team',
    author_email='team@vezor.io',
    url='https://github.com/vezor/vezor-python',
    packages=find_packages(),
    py_modules=['vezor_cli', 'config', 'supabase_client'],
    install_requires=[
        'requests>=2.31.0',
        'click>=8.1.7',
        'PyYAML>=6.0.1',
        'rich>=13.7.0',
        'keyring>=24.3.0',
        'supabase>=2.0.0',
    ],
    entry_points={
        'console_scripts': [
            'vezor=vezor_cli:cli',
        ],
    },
    python_requires='>=3.8',
    classifiers=[
        'Development Status :: 4 - Beta',
        'Intended Audience :: Developers',
        'License :: OSI Approved :: MIT License',
        'Operating System :: OS Independent',
        'Programming Language :: Python :: 3',
        'Programming Language :: Python :: 3.8',
        'Programming Language :: Python :: 3.9',
        'Programming Language :: Python :: 3.10',
        'Programming Language :: Python :: 3.11',
        'Programming Language :: Python :: 3.12',
        'Topic :: Security',
        'Topic :: Software Development :: Libraries :: Python Modules',
    ],
    keywords='secrets management gitops security devops',
)
