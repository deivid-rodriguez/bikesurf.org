# -*- coding: utf-8 -*-
# Copyright (c) 2012 Fabian Barkhau <fabian.barkhau@gmail.com>                  
# License: MIT (see LICENSE.TXT file) 


from django.views.decorators.http import require_http_methods
from django.utils.translation import ugettext as _
from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404
from django.core.exceptions import PermissionDenied
from django.http import HttpResponseRedirect
from allauth.account.models import EmailAddress
from apps.account.models import Account
from apps.common.shortcuts import render_response
from apps.account import forms
from apps.account import control
from apps.link.models import Link


PROFILE_UPDATED = _("PROFILE_UPDATED")


@login_required
@require_http_methods(["GET", "POST"])
def set_passport(request):
    account = get_object_or_404(Account, user=request.user)
    if request.method == "POST":
        form = forms.SetPassport(request.POST, request.FILES)
        if form.is_valid():
            passport = form.cleaned_data["passport"]
            control.set_passport(account, passport)
            return HttpResponseRedirect("/accounts/profile/")
    else:
        form = forms.SetPassport()
    args = { 
        "form" : form, "form_title" : _("SET_PASSPORT"), 
        "cancel_url" : "/accounts/profile/", "multipart_form" : True
    }
    return render_response(request, "common/form.html", args)


@login_required
@require_http_methods(["GET", "POST"])
def link_delete(request, link_id):
    account = get_object_or_404(Account, user=request.user)
    link = get_object_or_404(Link, id=link_id)
    if request.method == "POST":
        form = forms.LinkDelete(request.POST, link=link, account=account)
        if form.is_valid():
            control.link_delete(account, link)
            return HttpResponseRedirect("/accounts/profile/")
    else:
        form = forms.LinkDelete(link=link, account=account)
    args = { 
        "form" : form, "form_title" : _("LINK_DELETE?"), 
        "form_subtitle" : link.get_label(), 
        "cancel_url" : "/accounts/profile/"
    }
    return render_response(request, "common/form.html", args)


@login_required
@require_http_methods(["GET", "POST"])
def link_create(request):
    account = get_object_or_404(Account, user=request.user)
    if request.method == "POST":
        form = forms.LinkCreate(request.POST, account=account)
        if form.is_valid():
            control.link_create(
                account, 
                form.cleaned_data["site"], 
                form.cleaned_data["profile"].strip(), 
            )
            return HttpResponseRedirect("/accounts/profile/")
    else:
        form = forms.LinkCreate(account=account)
    args = { 
        "form" : form, "cancel_url" : "/accounts/profile/", 
        "form_title" :  account, "form_subtitle" : _("ADD_LINK_SUBTITLE")
    }
    return render_response(request, "common/form.html", args)


@login_required
@require_http_methods(["GET"])
def profile(request):
    account = get_object_or_404(Account, user=request.user)
    primary = get_object_or_404(EmailAddress, user=request.user, primary=True)
    args = { "links" : account.links.all(), "primary_email" : primary.email }
    return render_response(request, "account/profile.html", args)


@login_required
@require_http_methods(["GET"])
def view(request, username):
    current_account = get_object_or_404(Account, user=request.user)
    view_account = get_object_or_404(Account, user__username=username)
    if not control.can_view_account(current_account, view_account):
        raise PermissionDenied
    args = { "view_account" : view_account, "links" : view_account.links.all() }
    return render_response(request, "account/view.html", args)


@login_required
@require_http_methods(["GET", "POST"])
def edit(request):
    account = get_object_or_404(Account, user=request.user)
    if request.method == "POST":
        form = forms.Edit(request.POST, account=account)
        if form.is_valid():
            control.edit(
                account, 
                form.cleaned_data["username"].strip(), 
                form.cleaned_data["first_name"].strip(), 
                form.cleaned_data["last_name"].strip(), 
                form.cleaned_data["mobile"].strip(), 
                form.cleaned_data["source"], 
                form.cleaned_data["description"].strip()
            )
            return HttpResponseRedirect("/accounts/profile/")
    else:
        form = forms.Edit(account=account)
    args = { 
        "form" : form, "cancel_url" : "/accounts/profile/", 
        "form_title" :  account, "form_subtitle" : _("USER_PRIVECY_INFORMATION")
    }
    return render_response(request, "common/form.html", args)


