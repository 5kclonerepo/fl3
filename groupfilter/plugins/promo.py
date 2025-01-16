#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# (c) Git: @jithumon | TG: @jithumon

import re
from urllib.parse import urlparse
from pyrogram import Client, filters
from groupfilter.db.promo_sql import add_promo, del_promo, get_promos
from groupfilter import ADMINS


def is_valid_url(url):
    parsed_url = urlparse(url)
    return all([parsed_url.scheme, parsed_url.netloc])


@Client.on_message(filters.command("addpromo") & filters.user(ADMINS))
async def add_promo_(bot, message):
    match = re.search(r'/addpromo\s+"?([^"]+)"?\s+(\S+)', message.text)
    if match:
        text = match.group(1).strip()
        link = match.group(2).strip()
        if not is_valid_url(link):
            await message.reply_text("Invalid URL for button")
            return
        promo = await add_promo(link, text)
        if not promo:
            await message.reply_text("Something went wrong while adding Promo to DB")
        else:
            await message.reply_text(
                f"Promo added successfully to DB with Button: `{text}` and Link: `{link}`"
            )
    else:
        await message.reply_text(
            'Usage: \n/addpromo "Button Text" URL\n\nExample: \n/addpromo "Amazon Link" https://amazon.com'
        )


@Client.on_message(filters.command("delpromo") & filters.user(ADMINS))
async def delete_promo(bot, message):
    data = message.text.split()
    if len(data) == 2:
        link = data[-1]
        delete = await del_promo(link)
        if not delete:
            await message.reply_text(
                "Something went wrong while deleting Promo, please check the link is proper and currently added in promo"
            )
        else:
            await message.reply_text(f"Promo deleted successfully for Link: `{link}`")
    else:
        await message.reply_text(
            "Usage: \n/delpromo URL\n\nExample: \n/delpromo https://amazon.com"
        )


@Client.on_message(filters.command("listpromos") & filters.user(ADMINS))
async def list_promo(bot, message):
    ads_list = await get_promos()
    if not ads_list:
        await message.reply_text("No promos found in the database.")
        return

    msg = "Here are all the active promos:\n\n"
    count = 0
    for ad in ads_list:
        count += 1
        msg += f"{count}.  Button: `{ad['btn_txt']}`\n   Link: `{ad['link']}`\n\n"

    await message.reply_text(msg)
