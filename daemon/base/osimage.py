#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
OSImage Class will handle all os image operations.
"""

__author__      = 'Sumit Sharma'
__copyright__   = 'Copyright 2022, Luna2 Project'
__license__     = 'GPL'
__version__     = '2.0'
__maintainer__  = 'Sumit Sharma'
__email__       = 'sumit.sharma@clustervision.com'
__status__      = 'Development'

from json import dumps
from time import sleep, time
from os import getpid, path
from random import randint
from concurrent.futures import ThreadPoolExecutor
from utils.status import Status
from utils.osimage import OsImage as OsImager
from utils.database import Database
from utils.log import Log
from utils.queue import Queue
from utils.helper import Helper
from utils.model import Model

class OSImage():
    """
    This class is responsible for all operations for osimage.
    """

    def __init__(self):
        """
        This constructor will initialize all required variables here.
        """
        self.logger = Log.get_logger()
        self.table = 'osimage'
        self.table_cap = 'OS Image'


    def get_all_osimages(self):
        """
        This method will return all the osimage in detailed format.
        """
        response, access_code = Model().get_record(
            table = self.table,
            table_cap = self.table_cap
        )
        return response, access_code


    def get_osimage(self, name=None):
        """
        This method will return requested osimage in detailed format.
        """
        response, access_code = Model().get_record(
            name = name,
            table = self.table,
            table_cap = self.table_cap
        )
        return response, access_code


    def get_osimage_member(self, name=None):
        """
        This method will return all the list of all the member node names for a osimage.
        """
        response, access_code = Model().get_member(
            name = name,
            table = self.table,
            table_cap = self.table_cap
        )
        return response, access_code


    def update_osimage(self, name=None, http_request=None):
        """
        This method will create or update a osimage.
        """
        data = {}
        create, update = False, False
        request_data = http_request.data
        if request_data:
            data = request_data['config']['osimage'][name]
            image = Database().get_record(None, 'osimage', f' WHERE name = "{name}"')
            if image:
                image_id = image[0]['id']
                if 'newosimage' in data:
                    newosimage = data['newosimage']
                    where = f' WHERE `name` = "{newosimage}"'
                    osimage_check = Database().get_record(None, 'osimage', where)
                    if osimage_check:
                        response = {'message': f'{newosimage} Already present in database'}
                        access_code = 404
                        return dumps(response), access_code
                    else:
                        data['name'] = data['newosimage']
                        del data['newosimage']
                        data['changed']=1
                update = True
            else:
                create = True

            osimage_columns = Database().get_columns('osimage')
            column_check = Helper().compare_list(data, osimage_columns)
            if column_check:
                if update:
                    where = [{"column": "id", "value": image_id}]
                    row = Helper().make_rows(data)
                    Database().update('osimage', row, where)
                    response = {'message': f'OS Image {name} updated'}
                    access_code = 204
                if create:
                    data['name'] = name
                    row = Helper().make_rows(data)
                    Database().insert('osimage', row)
                    response = {'message': f'OS Image {name} created'}
                    access_code = 201
            else:
                response = {'message': 'Columns are incorrect'}
                access_code = 400
        else:
            response = {'message': 'Did not received data'}
            access_code = 400
        return dumps(response), access_code


    def clone_osimage(self, name=None, http_request=None):
        """
        This method will clone a osimage.
        """
        data = {}
        items = {
            'dracutmodules',
            'grab_filesystems',
            'grab_exclude',
            'initrdfile',
            'kernelfile',
            'kernelmodules',
            'kerneloptions',
            'kernelversion',
            'distribution'
        }
        access_code = 500
        response = {"message": 'OS image copy failed. No sign of life of spawned thread'}
        request_data = http_request.data
        if request_data:
            data = request_data['config']['osimage'][name]
            bare=False
            if 'bare' in data:
                bare = data['bare']
                bare = Helper().make_bool(bare)
                del data['bare']
            image = Database().get_record(None, 'osimage', f' WHERE name = "{name}"')
            if image:
                if 'newosimage' in data:
                    newosimage = data['newosimage']
                    where = f' WHERE `name` = "{newosimage}"'
                    osimage_check = Database().get_record(None, 'osimage', where)
                    if osimage_check:
                        response = {'message': f'{newosimage} Already present in database'}
                        access_code = 404
                        return dumps(response), access_code
                    else:
                        data['name'] = data['newosimage']
                        for item in items:
                            if (item not in data) and item in image[0] and image[0][item]:
                                data[item]=image[0][item]
                        del data['newosimage']
                        if 'path' in data and data['path'] and path.exists(data['path']):
                            message = f"Destination path {data['path']} already exists."
                            response = {'message': message}
                            access_code = 404
                            return dumps(response), access_code
                else:
                    response = {'message': 'New OS Image name not provided'}
                    access_code = 400
                    return dumps(response), access_code
            else:
                response = {'message': f'OS Image {name} not present in the database'}
                access_code = 404
                return dumps(response), access_code

            osimage_columns = Database().get_columns('osimage')
            column_check = Helper().compare_list(data, osimage_columns)
            if column_check:
                row = Helper().make_rows(data)
                Database().insert('osimage', row)
                request_id  =str(time()) + str(randint(1001, 9999)) + str(getpid())
                if bare is not False:
                    task = f"clone_osimage:{name}:{data['name']}"
                    task_id, text = Queue().add_task_to_queue(task, 'osimage', request_id)
                else:
                    task = f"clone_n_pack_osimage:{name}:{data['name']}"
                    task_id, text = Queue().add_task_to_queue(task, 'osimage', request_id)
                if not task_id:
                    self.logger.info("config_osimage_clone GET cannot get queue_id")
                    response= {"message": f"OS image {name}->{data['name']} clone queuing failed."}
                    return dumps(response), access_code

                if text != "added":
                    # this means we already have an equal request in the queue
                    access_code = 200
                    message = f"osimage clone for {data['name']} already queued"
                    response = {"message": message, "request_id": text}
                    self.logger.info(f"my response [{response}]")
                    return dumps(response), access_code
                self.logger.info(f"config_osimage_clone GET added task to queue: {task_id}")
                message = f"queued clone osimage {name}->{data['name']} with queue_id {task_id}"
                Status().add_message(request_id, "luna", message)
                next_id = Queue().next_task_in_queue('osimage')
                if task_id == next_id:
                    executor = ThreadPoolExecutor(max_workers=1)
                    executor.submit(OsImager().osimage_mother, request_id)
                    executor.shutdown(wait=False)
                # we should check after a few seconds if there is a status update for us.
                # if so, that means mother is taking care of things
                sleep(1)
                where = f' WHERE request_id = "{request_id}"'
                status = Database().get_record(None , 'status', where)
                if status:
                    access_code = 200
                    message = f"osimage clone for {data['name']} queued"
                    response = {"message": message, "request_id": request_id}
            else:
                response = {'message': 'Columns are incorrect'}
                access_code = 400
        else:
            response = {'message': 'Did not received data'}
            access_code = 400
        return dumps(response), access_code


    def delete_osimage(self, name=None):
        """
        This method will delete a osimage.
        """
        response, access_code = Model().delete_record(
            name = name,
            table = self.table,
            table_cap = self.table_cap
        )
        return response, access_code


    def grab(self, node=None, http_request=None):
        """
        This method will grab a osimage.
        """
        data = {}
        access_code = 500
        request_data = http_request.data
        if request_data:
            data = request_data['config']['node'][node]
            bare=False
            if 'bare' in data:
                bare = Helper().make_bool(data['bare'])
            nodry = False
            # means default dry=True
            if 'nodry' in data:
                nodry = Helper().make_bool(data['nodry'])
            osimage = None
            if 'osimage' in data:
                osimage=data['osimage']
            else:
                image_details = Database().get_record_join(
                    ['osimage.name as osimagename', 'osimage.id as osimageid'],
                    ['osimage.id=node.osimageid'],
                    [f'node.name="{node}"']
                )
                if not image_details:
                    #meaning, node does not have osimage override. we check the group
                    image_details = Database().get_record_join(
                        ['osimage.name as osimagename', 'osimage.id as osimageid'],
                        ['group.id=node.groupid', 'osimage.id=group.osimageid'],
                        [f'node.name="{node}"']
                    )
                if image_details:
                    osimage=image_details[0]['osimagename']
                else:
                    access_code = 404
                    message = f"Grab failed for {osimage}. "
                    message += "This node have osimage or group configured?"
                    response = {"message": message}
                    return dumps(response), access_code

            request_id = str(time()) + str(randint(1001, 9999)) + str(getpid())
            task_id, text = None,None
            if (bare is not False) or (nodry is False):
                task = f'grab_osimage:{node}:{osimage}:{nodry}'
                task_id, text = Queue().add_task_to_queue(task, 'osimage', request_id)
            else:
                task = f'grab_n_pack_n_build_osimage:{node}:{osimage}:{nodry}'
                task_id, text = Queue().add_task_to_queue(task, 'osimage', request_id)
            if not task_id:
                self.logger.info("config_osimage_grab GET cannot get queue_id")
                response= {"message": f'OS image {osimage} grab queuing failed'}
                return dumps(response), access_code
            if text != "added":
                # this means we already have an equal request in the queue
                access_code = 200
                message = f"osimage grab for {osimage} already queued"
                response = {"message": message, "request_id": text}
                self.logger.info(f"my response [{response}]")
                return dumps(response), access_code

            self.logger.info(f"config_osimage_grab POST added task to queue: {task_id}")
            message = f"queued grab osimage {osimage} with queue_id {task_id}"
            Status().add_message(request_id, "luna", message)

            next_id = Queue().next_task_in_queue('osimage')
            if task_id == next_id:
                executor = ThreadPoolExecutor(max_workers=1)
                executor.submit(OsImager().osimage_mother, request_id)
                executor.shutdown(wait=False)
                # OsImager().osimage_mother(request_id)
                # we should check after a few seconds if there is a status update for us.
                # if so, that means mother is taking care of things
            sleep(1)
            status = Database().get_record(None , 'status', f' WHERE request_id = "{request_id}"')
            if status:
                access_code = 200
                message = f"osimage grab from {node} to {osimage} queued"
                response = {"message": message, "request_id": request_id}
            self.logger.info(f"my response [{response}]")
            return dumps(response), access_code
        response = {"message": "osimage grab missing data"}
        access_code = 404
        return dumps(response), access_code


    def push(self, entity_name=None, http_request=None):
        """
        This method will push a osimage.
        """
        data = {}
        access_code = 500
        request_data = http_request.data
        if request_data:
            data, to_group = None, False
            nodry = False
            # means default dry=True
            if 'nodry' in request_data['config']:
                nodry = Helper().make_bool(data['nodry'])
            if 'group' in request_data['config']:
                data = request_data['config']['group'][entity_name]
                to_group = True
            else:
                data = request_data['config']['node'][entity_name]
            osimage=None
            if 'osimage' in data:
                osimage=data['osimage']
            else:
                image_details = None
                if to_group is True:
                    image_details = Database().get_record_join(
                        ['osimage.name as osimagename', 'osimage.id as osimageid'],
                        ['osimage.id=group.osimageid'],
                        [f'`group`.name="{entity_name}"']
                    )
                else:
                    image_details = Database().get_record_join(
                        ['osimage.name as osimagename', 'osimage.id as osimageid'],
                        ['osimage.id=node.osimageid'],
                        [f'node.name="{entity_name}"']
                    )
                    if not image_details:
                        # meaning, node does not have osimage override. we check the group
                        image_details = Database().get_record_join(
                            ['osimage.name as osimagename', 'osimage.id as osimageid'],
                            ['group.id=node.groupid', 'osimage.id=group.osimageid'],
                            [f'node.name="{entity_name}"']
                        )
                if image_details:
                    osimage=image_details[0]['osimagename']
                else:
                    access_code = 404
                    message = f"Push failed for {osimage}. "
                    message += "No osimage configured for this node or group?"
                    response = {"message": message}
                    return dumps(response), access_code

            request_id = str(time()) + str(randint(1001, 9999)) + str(getpid())
            task_id, text = None, None
            if to_group is True:
                task = f'push_osimage_to_group:{entity_name}:{osimage}:{nodry}'
                task_id, text = Queue().add_task_to_queue(task, 'osimage', request_id)
            else:
                task = f'push_osimage_to_node:{entity_name}:{osimage}:{nodry}'
                task_id, text = Queue().add_task_to_queue(task, 'osimage', request_id)
            if not task_id:
                self.logger.info("config_osimage_push POST cannot get queue_id")
                response= {"message": f'OS image {osimage} push queuing failed'}
                return dumps(response), access_code
            if text != "added":
                # this means we already have an equal request in the queue
                access_code = 200
                message = f"osimage push for {osimage} already queued"
                response = {"message": message, "request_id": text}
                self.logger.info(f"my response [{response}]")
                return dumps(response), access_code

            self.logger.info(f"config_osimage_push POST added task to queue: {task_id}")
            message = f"queued push osimage {osimage} with queue_id {task_id}"
            Status().add_message(request_id, "luna", message)

            next_id = Queue().next_task_in_queue('osimage')
            if task_id == next_id:
                executor = ThreadPoolExecutor(max_workers=1)
                executor.submit(OsImager().osimage_mother, request_id)
                executor.shutdown(wait=False)
                # OsImager().osimage_mother(request_id)
                # we should check after a few seconds if there is a status update for us.
                # if so, that means mother is taking care of things
            sleep(1)
            status = Database().get_record(None , 'status', f' WHERE request_id = "{request_id}"')
            if status:
                access_code = 200
                message = f"osimage push from {entity_name} to {osimage} queued"
                response = {"message": message, "request_id": request_id}
            self.logger.info(f"my response [{response}]")
            return dumps(response), access_code
        response = {"message": "osimage push missing data"}
        access_code = 404
        return dumps(response), access_code


    def pack(self, name=None):
        """
        This method will pack requested osimage.
        """
        access_code = 500
        response = {"message": f'OS image {name} packing failed. No sign of life of spawned thread'}
        # Antoine
        image = Database().get_record(None , 'osimage', f' WHERE name = "{name}"')
        force = False
        if image and 'changed' in image[0] and image[0]['changed']:
            force=True
            where = [{"column": "name", "value": {name}}]
            row = [{"column": "changed", "value": '0'}]
            Database().update('osimage', row, where)
        request_id = str(time()) + str(randint(1001, 9999)) + str(getpid())
        task = f'pack_n_build_osimage:{name}'
        queue_id, queue_response = Queue().add_task_to_queue(task, 'osimage', request_id, force)
        if not queue_id:
            self.logger.info("config_osimage_pack GET cannot get queue_id")
            response= {"message": f'OS image {name} pack queuing failed'}
            return dumps(response), access_code
        if queue_response != "added":
            # this means we already have an equal request in the queue
            access_code = 200
            message = f"osimage pack for {name} already queued"
            response = {"message": message, "request_id": queue_response}
            self.logger.info(f"my response [{response}]")
            return dumps(response), access_code

        self.logger.info(f"config_osimage_pack GET added task to queue: {queue_id}")
        message = f"queued pack osimage {name} with queue_id {queue_id}"
        Status().add_message(request_id, "luna", message)

        next_id = Queue().next_task_in_queue('osimage')
        if queue_id == next_id:
            executor = ThreadPoolExecutor(max_workers=1)
            executor.submit(OsImager().osimage_mother,request_id)
            executor.shutdown(wait=False)
            # OsImager().osimage_mother(request_id)
            # we should check after a few seconds if there is a status update for us.
            # if so, that means mother is taking care of things
        sleep(1)
        status = Database().get_record(None , 'status', f' WHERE request_id = "{request_id}"')
        if status:
            access_code = 200
            response = {"message": f"osimage pack for {name} queued", "request_id": request_id}
        self.logger.info(f"my response [{response}]")
        return dumps(response), access_code


    def change_kernel(self, name=None, http_request=None):
        """
        This method will change the kernel of an image and pack again that image.
        """
        data = {}
        request_data = http_request.data
        if request_data:
            data = request_data['config']['osimage'][name]
            image = Database().get_record(None, 'osimage', f' WHERE name = "{name}"')
            if image:
                osimage_columns = Database().get_columns('osimage')
                column_check = Helper().compare_list(data, osimage_columns)
                if column_check:
                    # TODO
                    # changed=1
                    # request_check = Helper().pack(name)
                    # discussed - pending
                    response = {'message': f'OS Image {name} Kernel updated'}
                    access_code = 204
                else:
                    response = {'message': 'Columns are incorrect'}
                    access_code = 400
            else:
                response = {'message': f'OS Image {name} does not exist'}
                access_code = 404
                return dumps(response), access_code
        else:
            response = {'message': 'Did not received data'}
            access_code = 400
        return dumps(response), access_code


    def get_status(self, request_id=None):
        """
        This method will get the exact status from queue, depends on the request ID.
        """
        access_code = 404
        response = {'message': 'No data for this request'}
        status = Database().get_record(None , 'status', f' WHERE request_id = "{request_id}"')
        if status:
            message = []
            for record in status:
                if 'read' in record:
                    if record['read'] == 0:
                        if 'message' in record:
                            if record['message'] == "EOF":
                                # Database().delete_row(
                                #     'status',
                                #     [{"column": "request_id", "value": request_id}]
                                # )
                                Status().del_messages(request_id)
                            else:
                                created, *_ = (record['created'].split('.') + [None])
                                message.append(created + " :: " + record['message'])
            response = {'message': (';;').join(message) }
            Status().mark_messages_read(request_id)
            access_code = 200
        return dumps(response), access_code
