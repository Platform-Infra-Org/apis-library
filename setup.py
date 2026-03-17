from setuptools import setup, find_packages

setup(
    name='tashtiot_apis_library',
    version='0.3.10',
    packages=find_packages(exclude=['*test*'], where='src'),
    package_dir={'':'src'},
    package_data=
    {"tashtiot_apis_library": ["static/*"] },

    license='Tashtiot Apis Library License',
    author='Elad Baruch and Alon Elimelech',
    description='Common utilities for Tashtiot Apis usage',
    url='https://bitbucket.app.com/projects/TAPI/repos/apis-library',
    install_requires=[ 
        'fastapi>=0.115.6',
        'pydantic>=1.8.2',
        'requests>=2.32.3',
        'prometheus-client>=0.20.0',
        'uvicorn>=0.22.0',
        'pytest>=7.4.3',
        'coverage>=7.5.2',
        'httpx>=0.27.2',
        'pytest-cov>=5.0.0',
        'pytest-mock>=3.6.0',
        'pyyaml>=6.0.1',
        'psutil>=5.9.7',
        'starlette>=0.41.3',
        'starlette-exporter>=0.21.0',
        'PyJWT>=2.9.0'
        ],
)
