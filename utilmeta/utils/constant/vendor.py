from ..datastructure import Static


class DB(Static):
    PostgreSQL = 'postgresql'
    MySQL = 'mysql'
    Oracle = 'oracle'
    SQLite = 'sqlite'


class AgentDevice(Static):
    pc = 'pc'
    mobile = 'mobile'
    bot = 'bot'
    tablet = 'tablet'
    email = 'email'


class AgentBrowser(Static):
    chrome = 'chrome'
    firefox = 'firefox'
    safari = 'safari'
    edge = 'edge'
    opera = 'opera'
    ie = 'ie'  # Internet Explorer


class AgentOS(Static):
    mac = 'mac'
    windows = 'windows'
    linux = 'linux'
