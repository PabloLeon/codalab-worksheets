"""
Deployment for CodaLab Worksheets.
Usage: create a deployment.config file.
"""
from datetime import datetime
import logging
import logging.config
import os
import re
import sys
import time
import yaml
import json

from StringIO import StringIO
from fabric.api import (cd,
                        env,
                        execute,
                        get,
                        prefix,
                        put,
                        require,
                        task,
                        roles,
                        require,
                        run,
                        settings,
                        shell_env,
                        sudo)
from fabric.contrib.files import exists
from fabric.network import ssh
from fabric.utils import fastprint

logger = logging.getLogger('deployment')

############################################################

class DeploymentConfig(object):
    """
    Defines credentials and configuration values needed to deploy CodaLab.
    """
    def __init__(self, label, filename):
        self.label = label
        with open(filename, 'r') as f:
            info = yaml.load(f)
        self._dinfo = info['deployment']
        self._svc_global = self._dinfo['service-global']
        self._svc = self._dinfo['service-configurations'][label] if label is not None else {}

    def getLoggerDictConfig(self):
        """Gets Dict config for logging configuration."""
        if 'logging' in self._dinfo:
            return self._dinfo['logging']
        else:
            return None

    def getServicePrefix(self):
        """Gets the unique prefix used to build the name of services and other resources."""
        return self._svc_global['prefix']

    def getServiceCertificateAlgorithm(self):
        """Gets the algorithm for the service certificate."""
        return self._svc_global['certificate']['algorithm']

    def getServiceCertificateThumbprint(self):
        """Gets the thumbprint for the service certificate."""
        return self._svc_global['certificate']['thumbprint']

    def getServiceCertificateFilename(self):
        """Gets the local path of the file holding the service certificate."""
        return self._svc_global['certificate']['filename']

    def getServiceCertificateKeyFilename(self):
        """Gets the local path of the file holding the service certificate key."""
        return self._svc_global['certificate']['key-filename']

    def getServiceCertificateFormat(self):
        """Gets the format of the service certificate."""
        return self._svc_global['certificate']['format']

    def getServiceCertificatePassword(self):
        """Gets the password for the service certificate."""
        return self._svc_global['certificate']['password']

    def getVirtualMachineLogonUsername(self):
        """Gets the username to log into a virtual machine of the service deployment."""
        return self._svc_global['vm']['username']

    def getVirtualMachineLogonPassword(self):
        """Gets the password to log into a virtual machine of the service deployment."""
        return self._svc_global['vm']['password']

    def getEmailInfo(self):
        return self._svc_global['email']

    def getAdminEmail(self):
        return self._svc_global['admin-email']

    def getSupportEmail(self):
        return self._svc_global['support-email']

    def getServiceName(self):
        """Gets the cloud service name."""
        return "{0}{1}".format(self.getServicePrefix(), self.label)

    def getServiceOSImageName(self):
        """Gets the name of the OS image used to create virtual machines in the service deployment."""
        return self._svc['vm']['os-image']

    def getServiceInstanceCount(self):
        """Gets the number of virtual machines to create in the service deployment."""
        return self._svc['vm']['count']

    def getServiceInstanceRoleSize(self):
        """Gets the role size for each virtual machine in the service deployment."""
        return self._svc['vm']['role-size']

    def getServiceInstanceSshPort(self):
        """Gets the base SSH port value. If this value is N, the k-th web instance will have SSH port number (N+k)."""
        return self._svc['vm']['ssh-port']

    def getGitUser(self):
        """Gets the name of the Git user associated with the target source code repository."""
        return self._svc['git']['user']

    def getGitRepo(self):
        """Gets the name of the Git of the target source code repository."""
        return self._svc['git']['repo']

    def getGitTag(self):
        """Gets the Git tag defining the specific version of the source code."""
        return self._svc['git']['tag']

    def getDjangoInfo(self):
        """Gets the value of the Django secret key."""
        return self._svc['django']

    def getDatabaseAdminPassword(self):
        """Gets the password for the database admin."""
        return self._svc['database']['admin_password']

    def getSslCertificatePath(self):
        """Gets the path of the SSL certificate file to install."""
        return self._svc['ssl']['filename'] if 'ssl' in self._svc else ""

    def getSslCertificateKeyPath(self):
        """Gets the path of the SSL certificate key file to install."""
        return self._svc['ssl']['key-filename'] if 'ssl' in self._svc else ""

    def getSslCertificateInstalledPath(self):
        """Gets the path of the installed SSL certificate file."""
        if len(self.getSslCertificatePath()) > 0:
            return "/etc/ssl/certs/%s" % os.path.basename(self.getSslCertificatePath())
        else:
            return ""

    def getSslCertificateKeyInstalledPath(self):
        """Gets the path of the installed SSL certificate key file."""
        if len(self.getSslCertificateKeyPath()) > 0:
            return "/etc/ssl/private/%s" % os.path.basename(self.getSslCertificateKeyPath())
        else:
            return ""

    def getSslRewriteHosts(self):
        """Gets the list of hosts for which HTTP requests are automatically re-written as HTTPS requests."""
        if 'ssl' in self._svc and 'rewrite-hosts' in self._svc['ssl']:
            return self._svc['ssl']['rewrite-hosts']
        return []

    def getWebHostnames(self):
        """
        Gets the list of web instances. Each name in the list if of the form '<service-name>.cloudapp.net:<port>'.
        """
        service_name = self.getServiceName()  # e.g., codalab
        vm_numbers = range(1, 1 + self.getServiceInstanceCount())  # e.g., prod
        ssh_port = self.getServiceInstanceSshPort()
        return ['{0}.cloudapp.net:{1}'.format(service_name, str(ssh_port + vm_number)) for vm_number in vm_numbers]

    def getBundleServiceGitUser(self):
        """Gets the name of the Git user associated with the target source code repository for bundles."""
        return self._svc['git-bundles']['user'] if 'git-bundles' in self._svc else ""

    def getBundleServiceGitRepo(self):
        """Gets the name of the Git of the target source code repository  for bundles."""
        return self._svc['git-bundles']['repo'] if 'git-bundles' in self._svc else ""

    def getBundleServiceGitTag(self):
        """Gets the Git tag defining the specific version of the source code  for bundles."""
        return self._svc['git-bundles']['tag'] if 'git-bundles' in self._svc else ""

    def getBundleServiceDatabaseName(self):
        """Gets the bundle service database name."""
        return self._svc['database']['bundle_db_name'] if 'bundle_db_name' in self._svc['database'] else ""

    def getBundleServiceDatabaseUser(self):
        """Gets the database username."""
        return self._svc['database']['bundle_user'] if 'bundle_user' in self._svc['database'] else ""

    def getBundleServiceDatabasePassword(self):
        """Gets the password for the database user."""
        return self._svc['database']['bundle_password'] if 'bundle_password' in self._svc['database'] else ""

############################################################

def getWebsiteConfig(config):
    """
    Generates the ~/.codalab/website-config.json file.
    """
    # Use the same allowed hosts for SSL and not SSL
    allowed_hosts = ssl_allowed_hosts = \
        config.getSslRewriteHosts() + \
        ['{0}.cloudapp.net'.format(config.getServiceName())]

    if len(config.getSslCertificateInstalledPath()) > 0:
        bundle_auth_scheme = "https"
    else:
        bundle_auth_scheme = "http"
    bundle_auth_host = allowed_hosts[0]
    bundle_auth_url = "{0}://{1}".format(bundle_auth_scheme, bundle_auth_host)

    return {
        'ALLOWED_HOSTS': allowed_hosts,
        'SSL_PORT': 443,
        'SSL_CERTIFICATE': config.getSslCertificateInstalledPath(),
        'SSL_CERTIFICATE_KEY': config.getSslCertificateKeyInstalledPath(),
        'SSL_ALLOWED_HOSTS': ssl_allowed_hosts,
        'django': config.getDjangoInfo(),
        'DJANGO_USE_UWSGI': True,
    }

############################################################
# Configuration (run every time)

@task
def using(path):
    """
    Specifies a location for the CodaLab configuration file (e.g., deployment.config)
    """
    env.cfg_path = path

@task
def config(label):
    """
    Reads deployment parameters for the given setup.
    label: Label identifying the desired setup (e.g., prod, test, etc.)
    """
    env.cfg_label = label
    print "Deployment label is:", env.cfg_label
    print "Loading configuration from:", env.cfg_path
    configuration = DeploymentConfig(label, env.cfg_path)
    print "Configuring logger..."
    logging.config.dictConfig(configuration.getLoggerDictConfig())
    env.roledefs = {'web' : configuration.getWebHostnames()}

    # Credentials
    env.user = configuration.getVirtualMachineLogonUsername()
    env.password = configuration.getVirtualMachineLogonPassword()
    env.key_filename = configuration.getServiceCertificateKeyFilename()

    # Repository
    env.git_codalab_tag = configuration.getGitTag()
    env.git_codalab_cli_tag = configuration.getBundleServiceGitTag()
    env.deploy_codalab_worksheets_dir = 'codalab-worksheets'
    env.deploy_codalab_cli_dir = 'codalab-cli'

    env.django_settings_module = 'codalab.settings'
    env.django_configuration = configuration.getDjangoInfo()['configuration']  # Prod or Dev
    env.config_http_port = '80'
    env.config_server_name = "{0}.cloudapp.net".format(configuration.getServiceName())

    env.configuration = True
    env.SHELL_ENV = {}

def setup_env():
    env.SHELL_ENV.update(dict(
        DJANGO_SETTINGS_MODULE=env.django_settings_module,
        DJANGO_CONFIGURATION=env.django_configuration,
        CONFIG_HTTP_PORT=env.config_http_port,
        CONFIG_SERVER_NAME=env.config_server_name,
    ))
    return prefix('source ~/%s/venv/bin/activate' % env.deploy_codalab_worksheets_dir), shell_env(**env.SHELL_ENV)

############################################################
# Installation (one-time)

@roles('web')
@task
def install():
    '''
    Install everything from scratch (idempotent).
    '''
    # Install Linux packages
    sudo('apt-get install -y git xclip python-virtualenv virtualenvwrapper zip')
    sudo('apt-get install -y python-dev libmysqlclient-dev libjpeg-dev')
    sudo('apt-get install -y supervisor')

    # Install latest stable version of NGINX
    # https://www.nginx.com/resources/wiki/start/topics/tutorials/install/#ubuntu-ppa
    sudo('apt-get install -y python-software-properties')  # ensures that we have add-apt-repository
    sudo('add-apt-repository ppa:nginx/stable')
    sudo('apt-get update')
    sudo('apt-get install -y nginx')

    # Install Node.js
    # https://nodejs.org/en/download/package-manager/#debian-and-ubuntu-based-linux-distributions
    sudo('curl -sL https://deb.nodesource.com/setup_4.x | bash -')
    sudo('apt-get install -y nodejs')

    # Setup repositories
    def ensure_repo_exists(repo, dest):
        run('[ -e %s ] || git clone %s %s' % (dest, repo, dest))
    ensure_repo_exists('https://github.com/codalab/codalab-worksheets', env.deploy_codalab_worksheets_dir)
    ensure_repo_exists('https://github.com/codalab/codalab-cli', env.deploy_codalab_cli_dir)

    # Initial setup
    with cd(env.deploy_codalab_worksheets_dir):
        run('git checkout %s' % env.git_codalab_tag)
        run('./setup.sh')
    with cd(env.deploy_codalab_cli_dir):
        run('git checkout %s' % env.git_codalab_cli_tag)
        run('./setup.sh server')

    # Deploy!
    _deploy()

@roles('web')
@task
def install_mysql(choice='all'):
    """
    Installs a local instance of MySQL of the web instance. This will only work
    if the number of web instances is one.

    choice: Indicates which assets to create/install:
        'mysql'      -> just install MySQL; don't create the databases
        'bundles_db' -> just create the bundle service database
        'all' or ''  -> install everything
    """
    require('configuration')
    if len(env.roledefs['web']) != 1:
        raise Exception("Task install_mysql requires exactly one web instance.")

    if choice == 'mysql':
        choices = {'mysql'}
    elif choice == 'bundles_db':
        choices = {'bundles_db'}
    elif choice == 'all':
        choices = {'mysql', 'bundles_db'}
    else:
        raise ValueError("Invalid choice: %s. Valid choices are: 'build', 'web' or 'all'." % (choice))

    configuration = DeploymentConfig(env.cfg_label, env.cfg_path)
    dba_password = configuration.getDatabaseAdminPassword()

    if 'mysql' in choices:
        sudo('DEBIAN_FRONTEND=noninteractive apt-get install -y mysql-server')
        sudo('mysqladmin -u root password {0}'.format(dba_password))

    if 'bundles_db' in choices:
        db_name = configuration.getBundleServiceDatabaseName()
        db_user = configuration.getBundleServiceDatabaseUser()
        db_password = configuration.getBundleServiceDatabasePassword()
        cmds = ["create database {0};".format(db_name),
                "create user '{0}'@'localhost' IDENTIFIED BY '{1}';".format(db_user, db_password),
                "GRANT ALL PRIVILEGES ON {0}.* TO '{1}'@'localhost' WITH GRANT OPTION;".format(db_name, db_user)]
        run('mysql --user=root --password={0} --execute="{1}"'.format(dba_password, " ".join(cmds)))


############################################################
# Deployment (after each update)

@roles('web')
@task
def supervisor(command):
    """
    Starts the supervisor on the web instances.
    """
    env_prefix, env_shell = setup_env()
    with env_prefix, env_shell, cd(env.deploy_codalab_worksheets_dir):
        if command == 'start':
            run('mkdir -p ~/logs')
            run('supervisord -c codalab/config/generated/supervisor.conf')
        elif command == 'stop':
            run('supervisorctl -c codalab/config/generated/supervisor.conf stop all')
            run('supervisorctl -c codalab/config/generated/supervisor.conf shutdown')
        elif command == 'restart':
            run('supervisorctl -c codalab/config/generated/supervisor.conf restart all')
        else:
            raise 'Unknown command: %s' % command

@roles('web')
@task
def nginx_restart():
    """
    Restarts nginx on the web server.
    """
    sudo('/etc/init.d/nginx restart')

# Maintenance and diagnostics
@roles('web')
@task
def maintenance(mode):
    """
    Begin or end maintenance (mode is 'begin' or 'end')
    """
    modes = {'begin': '1', 'end': '0'}
    if mode not in modes:
        print "Invalid mode. Valid values are 'begin' or 'end'"
        sys.exit(1)

    require('configuration')
    env.SHELL_ENV['MAINTENANCE_MODE'] = modes[mode]

    # Update nginx.conf
    env_prefix, env_shell = setup_env()
    with env_prefix, env_shell, cd(env.deploy_codalab_worksheets_dir), cd('codalab'):
        run('python manage.py config_gen')

    nginx_restart()


@roles('web')
@task
def backup_db(backupdir='backup'):
    """
    Dump the MySQL tables.

    |backupdir| specifies the path to the directory where the mysqldump
    should be saved, relative to the HOME directory.

    Usage:
        venv/bin/fab using:deployment.config -f codalab-worksheets/deployment/fabfile.py config:wsprod backup_db:/codalabdata/backup
    """
    configuration = DeploymentConfig(env.cfg_label, env.cfg_path)
    db_name = configuration.getBundleServiceDatabaseName()
    db_user = configuration.getBundleServiceDatabaseUser()
    db_password = configuration.getBundleServiceDatabasePassword()
    dumpfile = os.path.join(backupdir, '{database}_{now:%Y_%m_%d_%H_%M_%S}.mysqldump'.format(
        database=db_name, now=datetime.now()))
    run('mysqldump --user={user} --password={password} '
        '--single-transaction --quick {database} > {out}'.format(
            database=db_name, user=db_user, password=db_password, out=dumpfile),
        shell=True)
    return dumpfile


@roles('web')
@task
def rebuild_db(backupdir='backup'):
    """
    Rebuild the MySQL tables from scratch by mysqldump-ing the contents,
    clearing out the data files, then reloading the data from the dump.
    Useful for defragmenting the tables if innodb_file_per_table is off.
    or to rebuild the tables after turning innodb_file_per_table on.

    |backupdir| specifies the path to the directory where the mysqldump
    should be saved, relative to the HOME directory.

    Usage:
        venv/bin/fab using:deployment.config -f codalab-worksheets/deployment/fabfile.py config:wsprod rebuild_db:backupdir=/tmp

    Notes:
    innodb_file_per_table is a boolean option for MySQL databases using the
    InnoDB engine. When it is on, InnoDB stores each table as its own file
    in the filesystem, and when it is off, all the tables are stored in a
    single file (usually with the filename `ibdata1`). The former allows disk
    space to be automatically reclaimed when tables are defragmented with
    the `OPTIMIZE TABLE` command, while the latter allows some disk space
    to be shared between tables. A full discussion of the advantages and
    disadvantages of this option can be found in the MySQL documentation.
    Enabling innodb_file_per_table after database creation will not
    automatically create the per-table files. Issuing `ALTER TABLE` with
    `ALGORITHM=COPY` for each table will create the files, but will not shrink
    the `ibdata1` file correspondingly. Thus the only option for reclaiming
    disk space after the fact is to use this rebuild procedure.
    innodb_file_per_table is enabled by default in MySQL 5.6.6 and higher.
    By default, the main MySQL configuration file is at `/etc/mysql/my.cnf`.
    """
    maintenance('begin')
    supervisor('stop')

    mysql_command = (
        'mysql --user={user} --password={password} '
        '--raw --silent --skip-column-names --no-auto-rehash '
        '--execute="{query}"'
    )

    # Get the MySQL data directory
    configuration = DeploymentConfig(env.cfg_label, env.cfg_path)
    db_name = configuration.getBundleServiceDatabaseName()
    db_user = configuration.getBundleServiceDatabaseUser()
    db_password = configuration.getBundleServiceDatabasePassword()
    dba_password = configuration.getDatabaseAdminPassword()
    output = run(mysql_command.format(user='root',
                                      password=dba_password,
                                      query='SHOW VARIABLES LIKE \'datadir\''))
    mysqldir = re.search(u'datadir\s(\S+)', output).group(1)

    # Dump the MySQL tables
    dumpfile = backup_db(backupdir)

    # Drop entire database
    run(mysql_command.format(user='root',
                             password=dba_password,
                             query='DROP DATABASE ' + db_name))

    # Clean out uncommitted transactions and shutdown MySQL
    run(mysql_command.format(user='root',
                             password=dba_password,
                             query='SET GLOBAL innodb_fast_shutdown = 0'.format(db_name)))
    sudo('service mysql stop')

    # Remove MySQL data files
    for f in ['ibdata1', 'ib_logfile0', 'ib_logfile1']:
        sudo('rm ' + os.path.join(mysqldir, f))

    # Restart MySQL and wait for it to boot up
    sudo('service mysql start')
    time.sleep(2)

    # Recreate database and load dumped data
    cmds = ["CREATE DATABASE {0};".format(db_name),
            "GRANT ALL PRIVILEGES ON {0}.* TO '{1}'@'localhost' WITH GRANT OPTION;".format(db_name, db_user)]
    run(mysql_command.format(user='root', password=dba_password, query=" ".join(cmds)))
    run('mysql --user={user} --password={password} {database} < {infile}'.format(
        database=db_name, user=db_user, password=db_password, infile=dumpfile),
        shell=True)

    # Restart services
    supervisor('start')
    maintenance('end')


@roles('web')
@task
def migrate_db(alembic_revision, git_tag=None):
    """
    Migrates database to the given alembic revision.
    Can also specify a git tag to checkout first, since alembic histories
    can differ depending on where we are in git history.
    It is probably a good idea to turn begin maintenance mode and stop the
    supervised processes before running this. We do not do so explicitly here
    because you might want to deploy a different branch right after migrating.
    """
    with cd(env.deploy_codalab_cli_dir):
        run('git fetch')
        run('git checkout %s' % (git_tag or env.git_codalab_cli_tag))
        run('git pull')
        run('venv/bin/alembic upgrade {rev} || venv/bin/alembic downgrade {rev}'.format(rev=alembic_revision))

@roles('web')
@task
def deploy():
    """
    Put a maintenance message, deploy, and then restore website.
    """
    maintenance('begin')
    supervisor('stop')
    _deploy()
    supervisor('start')
    maintenance('end')

def _deploy():
    # Update website
    with cd(env.deploy_codalab_worksheets_dir):
        run('git fetch')
        run('git checkout %s' % env.git_codalab_tag)
        run('git pull')
        run('./setup.sh')

    # Update bundle service
    with cd(env.deploy_codalab_cli_dir):
        run('git fetch')
        run('git checkout %s' % env.git_codalab_cli_tag)
        run('git pull')
        run('./setup.sh server')

    # Create website-config.json
    cfg = DeploymentConfig(env.cfg_label, env.cfg_path)
    buf = StringIO()
    json.dump(getWebsiteConfig(cfg), buf, sort_keys=True, indent=4, separators=(',', ': '))
    buf.write('\n')
    put(buf, '.codalab/website-config.json')

    # Update the website configuration
    with cd(env.deploy_codalab_worksheets_dir), cd('codalab'):
        # Generate configuration files (nginx, supervisord)
        run('./manage config_gen')
        # Put configuration files in place.
        sudo('ln -sf `pwd`/config/generated/nginx.conf /etc/nginx/sites-enabled/codalab.conf')
        sudo('ln -sf `pwd`/config/generated/supervisor.conf /etc/supervisor/conf.d/codalab.conf')

    # Install SSL certficates (/etc/ssl/certs/)
    require('configuration')
    if (len(cfg.getSslCertificateInstalledPath()) > 0) and (len(cfg.getSslCertificateKeyInstalledPath()) > 0):
        put(cfg.getSslCertificatePath(), cfg.getSslCertificateInstalledPath(), use_sudo=True)
        put(cfg.getSslCertificateKeyPath(), cfg.getSslCertificateKeyInstalledPath(), use_sudo=True)
    else:
        logger.info("Skipping certificate installation because both files are not specified.")

    # Configure the bundle server
    with cd(env.deploy_codalab_cli_dir), cd('codalab'), cd('bin'):
        # For generating the bundle_server_config.json file.
        run('./cl config server/engine_url mysql://%s:%s@localhost:3306/%s' % ( \
            cfg.getBundleServiceDatabaseUser(),
            cfg.getBundleServiceDatabasePassword(),
            cfg.getBundleServiceDatabaseName(),
        ))
        # Send out emails from here (e.g., for password reset)
        email_info = cfg.getEmailInfo()
        run('./cl config email/host %s' % email_info['host'])
        run('./cl config email/user %s' % email_info['user'])
        run('./cl config email/password %s' % email_info['password'])
        # Send notifications.
        run('./cl config server/admin_email %s' % cfg.getAdminEmail())
        run('./cl config server/support_email %s' % cfg.getSupportEmail())
        run('./cl config server/instance_name %s' % cfg.label)

    # Update database
    with cd(env.deploy_codalab_cli_dir):
        run('venv/bin/alembic upgrade head')

    # Set up the bundles database.
    with cd(env.deploy_codalab_cli_dir):
        run('scripts/create-root-user.py %s' % cfg.getDatabaseAdminPassword())
