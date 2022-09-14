import hashlib
import os
import logging
import json
import datetime
import subprocess
import constants
from time import sleep
from flask import Blueprint, request
from multiprocessing import Process, Queue
from util.db_util import DBConnection
from util.ssh_util import ssh_util
from common.common import common
from util.decorators_util import *
from common.log_manager import LogManager


custom_install_blueprint = Blueprint('custom_install', __name__)
LogManager.create_log(file_name="logs/" + str(__name__), log_name=str(__name__))
logger=LogManager.get_logger()


@custom_install_blueprint.route("/<string:token>/custominstall", methods=['GET', 'POST'])
@login_required
def custom_install(token):
    """
    User anonymous Artifactory
    Sample Request Windows
    Sample Request: {"start":"2022-02-21 02:38:57.000000","end":"2022-02-25 15:30:00.000000","idsid":"sumits4x","reservationid":"377238","admin":"1","clusterid":"68159","macaddress":"1c:69:7a:6e:f1:cb","purpose":"Test","deviceid":"10421","gateway":"10.221.183.1","fog":"10.221.183.5","zabbix":"10.221.183.9","labname":"pg2","region":"pg","platform":"thm","program":"adl","os":"windows","osversion":"10","hostname":"pg02ral00017","ipaddress":"10.158.80.137","software":"gvim-8.2.2835,dediprog,pippackage","pippackage":"[{\"name\": \"pexpect\", \"version\": \"4.2.0\"}, {\"name\": \"xmltodict\"}]"}
    Sample Request Ubuntu
    Sample Request: {"start":"2022-02-21 02:38:57.000000","end":"2022-02-25 15:30:00.000000","idsid":"sumits4x","reservationid":"377238","admin":"1","clusterid":"68159","macaddress":"1c:69:7a:6e:f1:cb","purpose":"Test","deviceid":"10421","gateway":"10.221.183.1","fog":"10.221.183.5","zabbix":"10.221.183.9","labname":"pg2","region":"pg","platform":"thm","program":"adl","os":"ubuntu","osversion":"21.04","hostname":"pg02ral00017","ipaddress":"10.221.183.84","software":"basic,docker,aptpackage,pippackage","aptpackage":"[{\"name\": \"apache2\"}, {\"name\": \"wget\"}]","pippackage":"[{\"name\": \"pexpect\", \"version\": \"4.2.0\"}, {\"name\": \"xmltodict\"}]"}
    """
    logger.info('---')
    results = {}
    gatewayIp = ""
    Packages = {}

    Request = request.json
    logger.info("Received Data: {}".format(Request))

    if "software" in Request:
        AnsbileTagSoftware = Request["software"]
    else:
        AnsbileTagSoftware = ""

    if "aptpackage" in Request:
        Packages["aptpackage"] = json.loads(Request["aptpackage"])
    if "yumpackage" in Request:
        Packages["yumpackage"] = json.loads(Request["yumpackage"])
    if "pippackage" in Request:
        Packages["pippackage"] = json.loads(Request["pippackage"])

    if Packages:
        PackagesDB = json.dumps(Packages)
    else:
        PackagesDB = ""

    timenow = str(datetime.datetime.today()).split(".", 1)[0]
    Reservation = {
        "idsid": Request['idsid'],
        "reservationid": Request['reservationid'],
        "deviceid": Request['deviceid'],
        "start": Request['start'],
        "end": Request['end'],
        "imagename": "",
        "ipaddress": Request["ipaddress"],
        "macaddress": Request["macaddress"],
        "clusterid": Request['clusterid'],
        "hostname": Request['hostname'],
        "status": 0,
        "software": AnsbileTagSoftware,
        "packages": PackagesDB,
        "fogip": Request['fog'],
        "foggateway": Request['gateway'],
        "region": Request['region'],
        "created": timenow
    }
    QueryInsert = """INSERT INTO customapp set idsid = '{}', reservationid = '{}', deviceid = '{}', start = '{}', end = '{}', imagename = '{}', ipaddress = '{}',
    macaddress = '{}', clusterid = '{}', hostname = '{}', status = '{}', software = '{}', packages = '{}', fogip = '{}', foggateway = '{}', region = '{}', created = '{}'""".format(
        Reservation['idsid'], Reservation['reservationid'], Reservation['deviceid'], Reservation['start'],   Reservation['end'], Reservation['imagename'],
        Reservation['ipaddress'], Reservation['macaddress'], Reservation['clusterid'], Reservation['hostname'], Reservation['status'], AnsbileTagSoftware,
        PackagesDB, Reservation['fogip'], Reservation['foggateway'], Reservation['region'], Reservation['created'])
    QueryInsert = QueryInsert.replace("\n", "")
    try:
        InsertID = DBConnection().executeInsertOrDelQuery(QueryInsert)
        logger.info("Custom Installation Request, DB ID: {}".format(str(InsertID)))
    except Exception as e:
        logger.error(e)
        logger.error("Database Insert Failed in customapp.")
        results = {"message": "Failed: {}".format(e)}
        return results, 400

    AnsibleVariables = {
        "platform": Request["platform"],
        "program": Request["program"],
        "region": Request["region"],
        "os": Request["os"],
        "fog": Request["fog"],
        "zabbix": Request["zabbix"],
        "ipaddress": Request["ipaddress"],
        "osversion": Request["osversion"],
        "hostname": Request["hostname"]
    }
    AnsibleVariables = dict((k.lower(), v.lower()) for k,v in AnsibleVariables.items())

    if Packages:
        AnsibleVariables = {**AnsibleVariables, **Packages}

    fog = False
    queue = Queue()
    process = Process(target=common.ansibleplay, args=(queue, fog, AnsibleVariables, AnsbileTagSoftware))
    process.start()
    logger.info("Schedule job status ====>>> {}".format(str(process.is_alive())))

    if process.is_alive():
        logger.info("Job queue status ====>>> {}".format(str(queue.get())))
    result = {"message": "Ansible Installation is Running."}
    return result, 200
