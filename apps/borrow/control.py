# -*- coding: utf-8 -*-
# Copyright (c) 2012 Fabian Barkhau <fabian.barkhau@gmail.com>                  
# License: MIT (see LICENSE.TXT file) 


import datetime
from django.core.exceptions import PermissionDenied

from apps.borrow.models import Borrow
from apps.borrow.models import Rating
from apps.borrow.models import Log
from apps.team import control as team_control


def active_borrows_in_timeframe(bike, start, finish, exclude=None):
    """ Returns borrows in the given timeframe. finish is inclusive! """
    qs = Borrow.objects.filter(bike=bike, active=True)
    qs = qs.exclude(finish__lt=start, start__gt=finish)
    if exclude:
        qs = qs.exclude(id=exclude.id)
    borrows = list(qs)
    return borrows


def _tie_chain(borrow): # TODO give proper name
    """ Pass the borrow being removed from the chain.
        Updates previous and next borrows src and dest to match each other. """
    prev_borrow = _prev_borrow(borrow.bike, borrow.start)
    next_borrow = _next_borrow(borrow.bike, borrow.finish)
    if prev_borrow and next_borrow and prev_borrow.dest != next_borrow.src:
        next_borrow.src = prev_borrow.dest
        next_borrow.save()
        _log(None, borrow, "", "EDIT")


def _next_borrow(bike, finish):
    qs = Borrow.objects.filter(active=True, start__gt=finish)
    borrows = list(qs.order_by("start")[:1]) # order and limit
    return borrows and borrows[0] or None                  


def _prev_borrow(bike, start):
    qs = Borrow.objects.filter(active=True, finish__lt=start)
    borrows = list(qs.order_by("-finish")[:1]) # order and limit
    return borrows and borrows[0] or None                  


def _log(account, borrow, note, action):
    log = Log()
    log.borrow = borrow
    log.initiator = account
    log.action = action
    log.note = note
    log.save()
    return log


#########
# LISTS #
#########


def incoming_list(account):
    today = datetime.datetime.now().date()
    return Borrow.objects.filter(active=True, finish__gte=today, 
                                 dest__responsable=account)


def outgoing_list(account):
    today = datetime.datetime.now().date()
    return Borrow.objects.filter(active=True, start__gte=today, 
                                 src__responsable=account)


##############
# RESPONDING #
##############


def can_respond(account, borrow):
    if borrow.state != "REQUEST":
        return False # borrow must be in request state
    if not team_control.is_member(account, borrow.team):
        return False # not a member
    return True


def response_is_allowed(account, borrow, state):
    if not can_respond(account, borrow):
        return False
    if state == "REJECTED":
        return True
    today = datetime.datetime.now().date()
    if borrow.finish <= today:
        return False # to late
    if not can_borrow(borrow.bike):
        return False
    if active_borrows_in_timeframe(borrow.bike, borrow.start, borrow.finish):
        return False
    return True


def respond(account, borrow, state, note):
    if not response_is_allowed(account, borrow, state):
        raise PermissionDenied
    borrow.state = state
    borrow.active = state != "REJECTED"
    if state != "REJECTED": # set stations
        prev_borrow = _prev_borrow(borrow.bike, borrow.start)
        next_borrow = _next_borrow(borrow.bike, borrow.finish)
        borrow.src = prev_borrow and prev_borrow.dest or borrow.bike.station
        borrow.dest = next_borrow and next_borrow.src or borrow.bike.station
    borrow.save()
    log = _log(account, borrow, note, "RESPOND")
    return borrow


#############
# CANCELING #
#############


def can_cancel(account, borrow):
    borrow_started = borrow.start <= datetime.datetime.now().date()
    is_lender = team_control.is_member(account, borrow.team)
    is_borrower = account == borrow.borrower
    lender_cancel_allowed = borrow.state in ["MEETUP", "ACCEPTED"]
    borrower_cancel_allowed = borrow.state in ["REQUEST", "MEETUP", "ACCEPTED"] 
    return (is_borrower and borrower_cancel_allowed or 
            is_lender and lender_cancel_allowed and not borrow_started)


def cancel(account, borrow, note):
    if not can_cancel(account, borrow):
        raise PermissionDenied
    borrow.state = "CANCELED"
    if borrow.active: # ensure borrow chain unbroken
        _tie_chain(borrow)
        borrow.src = None
        borrow.dest = None
    borrow.active = False
    borrow.save()
    log = _log(account, borrow, note, "CANCLE")
    return borrow


#################
# CREATE BORROW #
#################


def can_borrow(bike):
    return (bike.active and not bike.reserve and 
            bike.station and bike.station.active)


def creation_is_allowed(bike, start, finish, exclude=None):
    if not can_borrow(bike):
        return False
    # check timeframe
    today = datetime.datetime.now().date()
    if start <= today:
        return False
    if finish < start:
        return False
    if len(active_borrows_in_timeframe(bike, start, finish, exclude=exclude)):
        return False
    return True


def create(account, bike, start, finish, note):
    if not creation_is_allowed(bike, start, finish):
        raise PermissionDenied
    borrow = Borrow()
    borrow.bike = bike
    borrow.team = bike.team
    borrow.borrower = account
    borrow.start = start
    borrow.finish = finish
    borrow.active = False
    borrow.state = "REQUEST"
    borrow.save()
    log = _log(account, borrow, note, "CREATE")
    return borrow


##########
# RATING #
##########


def _finish(borrow):
    if len(Rating.objects.filter(borrow=borrow)) != 2:
        return borrow # only finish when borrower and lender have rated
    borrow.state = "FINISHED"
    borrow.save()
    _log(None, borrow, "", "FINISHED")
    return borrow


def lender_can_rate(account, borrow):
    today = datetime.datetime.now().date()
    if not today > borrow.finish:
        return False # to soon
    if borrow.state not in ["MEETUP", "ACCEPTED"]:
        return False # wrong state
    if not team_control.is_member(account, borrow.team):
        return False # only members
    if len(Rating.objects.filter(borrow=borrow, originator='LENDER')):
        return False # already rated
    return True


def borrower_can_rate(account, borrow):
    today = datetime.datetime.now().date()
    if not today >= borrow.start:
        return False # to soon
    if borrow.state not in ["MEETUP", "ACCEPTED"]:
        return False # wrong state
    if account != borrow.borrower:
        return False # only borrower
    if len(Rating.objects.filter(borrow=borrow, originator='BORROWER')):
        return False # already rated
    return True


def lender_rate(account, borrow, rating_value, note):
    if not lender_can_rate(account, borrow):
        raise PermissionDenied
    rating = Rating()   
    rating.borrow = borrow
    rating.rating = rating_value
    rating.account = account
    rating.originator = "LENDER"
    rating.save()
    log = _log(account, borrow, note, "LENDER_RATE")
    return _finish(borrow)


def borrower_rate(account, borrow, rating_value, note):
    if not borrower_can_rate(account, borrow):
        raise PermissionDenied
    rating = Rating()   
    rating.borrow = borrow
    rating.rating = rating_value
    rating.account = account
    rating.originator = "BORROWER"
    rating.save()
    log = _log(account, borrow, note, "BORROWER_RATE")
    return _finish(borrow)


###########
# EDITING #
###########


def lender_can_edit(account, borrow):
    today = datetime.datetime.now().date()
    if borrow.state not in ["REQUEST", "ACCEPTED", "MEETUP"]:
        return False
    if borrow.start <= today:
        return False
    if account not in borrow.team.members.all():
        return False
    return True


def lender_can_edit_dest(account, borrow):
    if not lender_can_edit(account, borrow):
        return False
    if not borrow.active:
        return False
    return True


def borrower_can_edit(account, borrow):
    today = datetime.datetime.now().date()
    if borrow.state not in ["REQUEST", "ACCEPTED", "MEETUP"]:
        return False
    if borrow.start <= today:
        return False
    if account != borrow.borrower:
        return False
    return True


def borrower_edit_is_allowed(account, borrow, start, finish, bike):
    if not borrower_can_edit(account, borrow):
        return False
    if not creation_is_allowed(bike, start, finish, exclude=borrow):
        return False
    if bike.team != borrow.team or not bike.active:
        return False
    return True


def lender_edit_bike_is_allowed(account, borrow, bike):
    if not lender_can_edit(account, borrow):
        return False
    if bike.team != borrow.team or not bike.active:
        return False
    return True


def lender_edit_dest_is_allowed(account, borrow, dest):
    if not lender_can_edit_dest(account, borrow):
        return False
    if dest.team != borrow.team or not dest.active:
        return False
    return True


def borrower_edit(account, borrow, start, finish, bike, note):
    if (borrow.start == start and borrow.finish == finish 
            and borrow.bike == bike):
        return # nothing changed
    if not borrower_edit_is_allowed(account, borrow, start, finish, bike):
        raise PermissionDenied
    if borrow.active: # ensure borrow chain unbroken
        _tie_chain(borrow)
    borrow.start = start
    borrow.finish = finish
    borrow.bike = bike
    borrow.state = "REQUEST" # borrower edits require confirmation
    borrow.active = False
    borrow.save()
    _log(account, borrow, note, "EDIT")


def lender_edit_dest(account, borrow, dest, note):
    if borrow.dest == dest:
        return # nothing changed
    if not lender_edit_dest_is_allowed(account, borrow, dest):
        raise PermissionDenied
    next_borrow = _next_borrow(borrow.bike, borrow.finish)
    if next_borrow:
        next_borrow.src = dest
        next_borrow.save()
        _log(None, borrow, "", "EDIT")
    borrow.dest = dest
    borrow.save()
    _log(account, borrow, note, "EDIT")


def lender_edit_bike(account, borrow, bike, note):
    if borrow.bike == bike:
        return # nothing changed
    if not lender_edit_bike_is_allowed(account, borrow, bike):
        raise PermissionDenied
    if borrow.active: # fix borrow chains
        _tie_chain(borrow)
        prev_borrow = _prev_borrow(bike, borrow.start)
        next_borrow = _next_borrow(bike, borrow.finish)
        borrow.src = prev_borrow and prev_borrow.dest or bike.station
        borrow.dest = prev_borrow and prev_borrow.dest or bike.station
    borrow.bike = bike
    borrow.save()
    _log(account, borrow, note, "EDIT")


