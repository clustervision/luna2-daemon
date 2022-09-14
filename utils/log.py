# #!/usr/bin/env python3

# __author__      = "Sumit Sharma"
# __copyright__   = "Copyright 2022, Luna2 Project"
# __license__     = "GPL"
# __version__     = "1.0"
# __maintainer__  = "Sumit Sharma"
# __email__       = "sumit.sharma@clustervision.com"
# __status__      = "Production"

# """

# """
# import os
# import sys
# import logging
# from pathlib import Path
# from utils.constants import *

# if not LEVEL:
#     LEVEL = 0
# else:
#     levels = {"NOTSET": 0, "DEBUG": 10, "INFO": 20, "WARNING": 30, "ERROR": 40, "CRITICAL": 50}
#     LEVEL = levels[LEVEL.upper()]
# logging.basicConfig(filename=BASE_DIR+"/"+LOGFILE, format='%(asctime)s %(levelname)s: %(message)s', filemode='a', level=LEVEL)
# logger = logging.getLogger("luna2-daemon")
# logger.setLevel(LEVEL)
# formatter = logging.Formatter('%(asctime)s %(levelname)s: %(message)s')
# cnsl = logging.StreamHandler(sys.stdout)
# cnsl.setLevel(LEVEL)
# cnsl.setFormatter(formatter)
# logger.addHandler(cnsl)
# levels = {0: "NOTSET", 10: "DEBUG", 20: "INFO", 30: "WARNING", 40: "ERROR", 50: "CRITICAL"}
# logger.info('=============== Logger Level Set To [{}]==============='.format(levels[LEVEL]))

# def luna_logging(message, LEVEL):
#     match LEVEL:
#         case "debug" | 10:
#             return logger.debug(message)
#         case "info" | 20:
#             return logger.info(message)
#         case "warning" | 30:
#             return logger.warning(message)
#         case "error" | 40:
#             return logger.error(message)
#         case "critical" | 50:
#             return logger.critical(message)
#         case _:
#             print("Log Level isn't set, Kinldy choose debug or info or warning or error or critical")









#!/usr/bin/env python3

__author__      = "Sumit Sharma"
__copyright__   = "Copyright 2022, Luna2 Project"
__license__     = "GPL"
__version__     = "1.0"
__maintainer__  = "Sumit Sharma"
__email__       = "sumit.sharma@clustervision.com"
__status__      = "Production"

"""

"""
import os
import sys
import logging
from pathlib import Path
from utils.constants import *

class Log(object):

    def __init__(self):
        pass


    def init_log(self, LEVEL):
        if not LEVEL:
            LEVEL = 0
        else:
            levels = {"NOTSET": 0, "DEBUG": 10, "INFO": 20, "WARNING": 30, "ERROR": 40, "CRITICAL": 50}
            LEVEL = levels[LEVEL.upper()]
        logging.basicConfig(filename=BASE_DIR+"/"+LOGFILE, format='%(asctime)s %(levelname)s: %(message)s', filemode='a', level=LEVEL)
        self.logger = logging.getLogger("luna2-daemon")
        self.logger.setLevel(LEVEL)
        formatter = logging.Formatter('%(asctime)s %(levelname)s: %(message)s')
        cnsl = logging.StreamHandler(sys.stdout)
        cnsl.setLevel(LEVEL)
        cnsl.setFormatter(formatter)
        self.logger.addHandler(cnsl)
        levels = {0: "NOTSET", 10: "DEBUG", 20: "INFO", 30: "WARNING", 40: "ERROR", 50: "CRITICAL"}
        self.logger.info('=============== Logger Level Set To [{}]==============='.format(levels[LEVEL]))
        return self.logger


    def luna_logging(self, message, log_level):
        match log_level:
            case "debug" | 10:
                return self.logger.debug(message)
            case "info" | 20:
                return self.logger.info(message)
            case "warning" | 30:
                return self.logger.warning(message)
            case "error" | 40:
                return self.logger.error(message)
            case "critical" | 50:
                return self.logger.critical(message)
            case _:
                print("Log Level isn't set, Kinldy choose debug or info or warning or error or critical")






















# #!/usr/bin/env python3

# __author__      = "Sumit Sharma"
# __copyright__   = "Copyright 2022, Luna2 Project"
# __license__     = "GPL"
# __version__     = "1.0"
# __maintainer__  = "Sumit Sharma"
# __email__       = "sumit.sharma@clustervision.com"
# __status__      = "Production"

# """

# """
# import os
# import sys
# import logging
# from pathlib import Path
# from utils.constants import *

# class Log(object):

#     def __init__(self):
#         pass


#     def init_log(self, log_level, logfile):
#         if hasattr(self, 'logger'):
#             return self.logger
#         else:
#             if not log_level:
#                 log_level = 0
#             else:
#                 levels = {"NOTSET": 0, "DEBUG": 10, "INFO": 20, "WARNING": 30, "ERROR": 40, "CRITICAL": 50}
#                 log_level = levels[log_level.upper()]
#             logging.basicConfig(filename=BASE_DIR+"/"+logfile, format='%(asctime)s %(levelname)s: %(message)s', filemode='a', level=log_level)
#             self.logger = logging.getLogger("luna2-daemon")
#             self.logger.setLevel(log_level)
#             formatter = logging.Formatter('%(asctime)s %(levelname)s: %(message)s')
#             cnsl = logging.StreamHandler(sys.stdout)
#             cnsl.setLevel(log_level)
#             cnsl.setFormatter(formatter)
#             self.logger.addHandler(cnsl)
#             self.logger.info('=============== Logger Level Set To [{}]==============='.format(log_level))
#             return self.logger


#     def luna_logging(self, message, log_level):
#         match log_level:
#             case "debug" | 10:
#                 return self.logger.debug(message)
#             case "info" | 20:
#                 return self.logger.info(message)
#             case "warning" | 30:
#                 return self.logger.warning(message)
#             case "error" | 40:
#                 return self.logger.error(message)
#             case "critical" | 50:
#                 return self.logger.critical(message)
#             case _:
#                 print("Log Level isn't set, Kinldy choose debug or info or warning or error or critical")

