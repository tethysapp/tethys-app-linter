#!/opt/conda/envs/tethys/bin/python

import sys
import os
from glob import glob
import subprocess
import yaml

# variables
errors = False
python_version = sys.version[:3]
install_file = ''
app_python_package = ''
repo_owner, repo_name = sys.argv[1].split('/')
workspace = sys.argv[2]

# use test_app if running on self
if repo_name == 'tethys-app-linter':
    repo_name = 'tethysapp-test_app'
    workspace = os.path.join('/', repo_name)

# check setup.py exists
print('Verifying that setup.py exists.')
if os.path.isfile(os.path.join(workspace, 'setup.py')):
    print("setup.py file exists.")
else:
    errors = True
    print('setup.py not found.')

# check install.yml exists
print('Verifying that install.yml exists.')
if os.path.isfile(os.path.join(workspace, 'install.yml')):
    install_file = os.path.join(workspace, 'install.yml')
    print("install.yml file exists.")
elif os.path.isfile(os.path.join(workspace, 'install.yaml')):
    install_file = os.path.join(workspace, 'install.yaml')
    print("install.yaml file exists.")
else:
    errors = True
    print("install.yml not found.")

if install_file:
    print("Validating install.yml.")
    try:
        with open(install_file, 'r') as f:
            yaml.safe_load(f)
    except Exception as e:
        print(e)

# check that all dependencies are included in "install.yml"
print('Verifying that all dependencies have been listed.')
if install_file:
    pipreqs_exec = '/opt/conda/envs/tethys/bin/pipreqs'
    # generate tethys_platform dependencies
    tethys_platform_dependencies = []
    tethys_platform_installation_path = glob(
        f'/opt/conda/envs/tethys/lib/python{python_version}/site-packages/tethys_platform*'
    )[0]
    with open(os.path.join(tethys_platform_installation_path, 'top_level.txt'), 'r') as f:
        tethys_libraries = f.read().splitlines()

    for lib in tethys_libraries:
        p0 = subprocess.Popen(
            f'{pipreqs_exec} /opt/conda/envs/tethys/lib/python{python_version}/site-packages/{lib} --print',
            stdout=subprocess.PIPE,
            shell=True
        )
        for req in p0.communicate()[0].splitlines():
            package, version = req.decode('utf-8').split('==')
            if package.lower() not in tethys_platform_dependencies:
                tethys_platform_dependencies.append(package.lower())

    requirements = []
    p1 = subprocess.Popen(
        f'{pipreqs_exec} {workspace} --print',
        stdout=subprocess.PIPE,
        shell=True
    )
    for req in p1.communicate()[0].splitlines():
        package, version = req.decode('utf-8').split('==')
        if package.lower() not in tethys_platform_dependencies:
            requirements.append(package.lower())

    listed_requirements = []
    with open(install_file, 'r') as f:
        install_file_contents = yaml.safe_load(f).get('requirements', {})
    if install_file_contents and install_file_contents['conda']['packages']:
        listed_requirements.extend(install_file_contents['conda']['packages'])
    if install_file_contents and install_file_contents['pip']:
        listed_requirements.extend(install_file_contents['pip'])

    requirements = set(requirements)
    listed_requirements = set(listed_requirements)

    if not requirements or listed_requirements.issubset(requirements):
        print('All requirements are listed.')
    else:
        errors = True
        requirement_diff = list(requirements.difference(listed_requirements))
        print(f'Missing requirements: {requirement_diff}')

# check that the app python package is the only directory in the app package directory
print('Verifying that the app python package is the only directory in the app package directory.')
if len(os.listdir(os.path.join(workspace, 'tethysapp'))) > 1:
    print('The app package contains directories other than the app python package')
else:
    app_python_package = os.listdir(os.path.join(workspace, 'tethysapp'))[0]

# check that there's not an __init__.py file at the release and app package directories
print('Verifying that the release package directory is not a python package.')
if os.path.isfile(os.path.join(workspace, '__init__.py')):
    errors = True
    print('Found "__init__.py" in the release package directory. Please remove it.')
elif os.path.isfile(os.path.join(workspace, 'tethysapp', '__init__.py')):
    errors = True
    print('Found "__init__.py" in the app package directory. Please remove it.')

# check that __init__.py in app python package is empty
if app_python_package:
    print('Verifying that the __init__.py file in the app python package is empty.')
    if os.path.isfile(os.path.join(workspace, 'tethysapp', app_python_package, '__init__.py')):
        with open(os.path.join(workspace, 'tethysapp', app_python_package, '__init__.py'), 'r') as f:
            if f.read():
                print('The app python package "__init__.py" file should be empty.')

# install the app
if app_python_package and not errors:
    print('Testing app installation.')
    p2 = subprocess.Popen(
        [f'cd {workspace} ; . /opt/conda/bin/activate tethys && python setup.py install'],
        stdout=subprocess.PIPE,
        shell=True
    )
    for l in p2.communicate()[0].decode('utf-8').splitlines():
        print(l)

# check that needed non-python files were properly added to the resource_files variable of setup.py
if app_python_package and not errors:
    print('Verifying that needed non-python files were properly added to the "resource_files" variable of setup.py')
    non_python_files_repo = []
    non_python_files_installation = []
    repo_python_package = os.path.join(workspace, 'tethysapp', app_python_package)
    installed_python_package = glob(
        f'/opt/conda/envs/tethys/lib/python{python_version}/site-packages/{repo_name.replace("-", "_")}*'
    )[0]

    for root, subdirs, files in os.walk(repo_python_package):
        for file in files:
            if not file.startswith('.') and not file.endswith('.py'):
                non_python_files_repo.append(file)

    for root, subdirs, files in os.walk(installed_python_package):
        for file in files:
            if not file.endswith('.py'):
                non_python_files_installation.append(file)

    for file in non_python_files_repo:
        if file not in non_python_files_installation:
            print(f'The file "{file}" was not added to the "resource_files" variable in the setup.py.')
