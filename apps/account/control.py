# -*- coding: utf-8 -*-
# Copyright (c) 2012 Fabian Barkhau <fabian.barkhau@gmail.com>                  
# License: MIT (see LICENSE.TXT file) 


def edit(account, username, first_name, last_name, mobile, source, description):
    account.user.username = username
    account.user.first_name = first_name
    account.user.last_name = last_name
    account.user.save()
    account.mobile = mobile
    account.source = source
    account.description = description
    account.save()


