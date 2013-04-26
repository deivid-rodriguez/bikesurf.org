# -*- coding: utf-8 -*-
# Copyright (c) 2012 Fabian Barkhau <fabian.barkhau@gmail.com>                  
# License: MIT (see LICENSE.TXT file) 


from apps.team.models import Team
from apps.team.models import JoinRequest
from django.core.exceptions import PermissionDenied
from apps.common.shortcuts import uslugify


def is_member(account, team):
    return account in team.members.all()


def create(account, name, country):
    team = Team()
    team.name = name
    team.link = uslugify(name)
    team.country = country
    team.created_by = account
    team.updated_by = account
    team.save()
    team.members.add(account)
    # TODO require activation by site admin
    return team


def create_join_request(account, team, application):
    if is_member(account, team):
        raise PermissionDenied # already a member
    filters = {"team" : team, "requester" : account, "status" : "PENDING"}
    if len(JoinRequest.objects.filter(**filters)) > 0:
        raise PermissionDenied # already requested
    join_request = JoinRequest()
    join_request.team = team
    join_request.requester = account
    join_request.application = application
    join_request.save()
    return join_request


def process_join_request(account, team, join_request, response, status):
    if not is_member(account, team):
        raise PermissionDenied
    if join_request.status != "PENDING":
        raise PermissionDenied # already processed
    join_request.processor = account
    join_request.response = response
    join_request.status = status
    join_request.save()
    if join_request.status == 'ACCEPTED':
        join_request.team.members.add(join_request.requester)


