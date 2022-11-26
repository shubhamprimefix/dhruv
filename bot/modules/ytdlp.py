from threading import Thread
from telegram.ext import CommandHandler, CallbackQueryHandler
from time import sleep
from re import split as re_split

from bot import DOWNLOAD_DIR, dispatcher, config_dict, user_data, download_dict, LOGGER
from bot.helper.telegram_helper.message_utils import sendMessage, sendMarkup, editMessage
from bot.helper.telegram_helper.button_build import ButtonMaker
from bot.helper.ext_utils.bot_utils import get_readable_file_size, is_url, get_user_task
from bot.helper.mirror_utils.download_utils.yt_dlp_download_helper import YoutubeDLHelper
from bot.helper.telegram_helper.bot_commands import BotCommands
from bot.helper.telegram_helper.filters import CustomFilters
from .listener import MirrorLeechListener
from bot.helper.telegram_helper.button_build import ButtonMaker

listener_dict = {}

def _ytdl(bot, message, isZip=False, isLeech=False):
    user_id = message.from_user.id
    total_task = len(download_dict)
    USER_TASKS_LIMIT = config_dict['USER_TASKS_LIMIT']
    TOTAL_TASKS_LIMIT = config_dict['TOTAL_TASKS_LIMIT']
    if user_id != config_dict['OWNER_ID']:
        if TOTAL_TASKS_LIMIT == total_task:
            return sendMessage(f"Total task limit: {TOTAL_TASKS_LIMIT}\nTasks processing: {total_task}\n\nTotal limit exceeded!", bot ,message)
        if USER_TASKS_LIMIT == get_user_task(user_id):
            return sendMessage(f"User task limit: {USER_TASKS_LIMIT} \nYour tasks: {get_user_task(user_id)}\n\nUser limit exceeded!", bot ,message)
    if config_dict['BOT_PM'] and message.chat.type != 'private':
        buttons = ButtonMaker()	
        try:
            msg = f'Test msg.'
            send = bot.sendMessage(message.from_user.id, text=msg)
            send.delete()
        except Exception as e:
            LOGGER.warning(e)
            bot_d = bot.get_me()
            b_uname = bot_d.username
            uname = f'<a href="tg://user?id={message.from_user.id}">{message.from_user.first_name}</a>'
            botstart = f"http://t.me/{b_uname}"
            buttons.buildbutton("Click here to start me!", f"{botstart}")
            startwarn = f"Dear {uname},\nI found that you haven't started me in PM yet.\n\n" \
                        f"Start me in PM so that i can send a copy of your Files/Links in your PM."
            message = sendMarkup(startwarn, bot, message, buttons.build_menu(1))
            return

    mssg = message.text
    user_id = message.from_user.id
    msg_id = message.message_id
    qual = ''
    select = False
    multi = 0
    index = 1
    link = ''

    args = mssg.split(maxsplit=2)
    if len(args) > 1:
        for x in args:
            x = x.strip()
            if x == 's':
               select = True
               index += 1
            elif x.strip().isdigit():
                multi = int(x)
                mi = index
        if multi == 0:
            args = mssg.split(maxsplit=index)
            if len(args) > index:
                link = args[index].strip()
                if link.startswith(("|", "pswd:", "opt:")):
                    link = ''

    name = mssg.split('|', maxsplit=1)
    if len(name) > 1:
        if 'opt:' in name[0] or 'pswd:' in name[0]:
            name = ''
        else:
            name = re_split('pswd:|opt:', name[1])[0].strip()
    else:
        name = ''

    pswd = mssg.split(' pswd: ')
    pswd = pswd[1].split(' opt: ')[0] if len(pswd) > 1 else None

    opt = mssg.split(' opt: ')
    opt = opt[1] if len(opt) > 1 else ''

    if message.from_user.username:
        tag = f"@{message.from_user.username}"
    else:
        tag = message.from_user.mention_html(message.from_user.first_name)

    reply_to = message.reply_to_message
    if reply_to is not None:
        if len(link) == 0:
            link = reply_to.text.split(maxsplit=1)[0].strip()
        if reply_to.from_user.username:
            tag = f"@{reply_to.from_user.username}"
        else:
            tag = reply_to.from_user.mention_html(reply_to.from_user.first_name)

    if not is_url(link):
        help_msg = "Send link along with command or by replying to the link by command."
        return sendMessage(help_msg, bot, message)

    listener = MirrorLeechListener(bot, message, isZip, isLeech=isLeech, pswd=pswd, tag=tag)
    ydl = YoutubeDLHelper(listener)
    try:
        result = ydl.extractMetaData(link, name, opt, True)
    except Exception as e:
        msg = str(e).replace('<', ' ').replace('>', ' ')
        return sendMessage(tag + " " + msg, bot, message)
    if not select:
        user_dict = user_data.get(user_id, False)
        if 'format:' in opt:
            opts = opt.split('|')
            for f in opts:
                if f.startswith('format:'):
                    qual = f.split('format:', 1)[1]
        elif user_dict and user_dict.get('yt_ql', False):
            qual = user_dict['yt_ql']
        elif config_dict['YT_DLP_QUALITY']:
            qual = config_dict['YT_DLP_QUALITY']
    if qual:
        playlist = 'entries' in result
        Thread(target=ydl.add_download, args=(link, f'{DOWNLOAD_DIR}{msg_id}', name, qual, playlist, opt)).start()
    else:
        buttons = ButtonMaker()
        best_video = "bv*+ba/b"
        best_audio = "ba/b"
        formats_dict = {}
        if 'entries' in result:
            for i in ['144', '240', '360', '480', '720', '1080', '1440', '2160']:
                video_format = f"bv*[height<={i}][ext=mp4]+ba[ext=m4a]/b[height<={i}]"
                b_data = f"{i}|mp4"
                formats_dict[b_data] = video_format
                buttons.sbutton(f"{i}-mp4", f"qu {msg_id} {b_data} t")
                video_format = f"bv*[height<={i}][ext=webm]+ba/b[height<={i}]"
                b_data = f"{i}|webm"
                formats_dict[b_data] = video_format
                buttons.sbutton(f"{i}-webm", f"qu {msg_id} {b_data} t")
            buttons.sbutton("MP3", f"qu {msg_id} mp3 t")
            buttons.sbutton("Best Videos", f"qu {msg_id} {best_video} t")
            buttons.sbutton("Best Audios", f"qu {msg_id} {best_audio} t")
            buttons.sbutton("Cancel", f"qu {msg_id} cancel")
            YTBUTTONS = buttons.build_menu(3)
            listener_dict[msg_id] = [listener, user_id, link, name, YTBUTTONS, opt, formats_dict]
            bmsg = sendMarkup('Choose Playlist Videos Quality:', bot, message, YTBUTTONS)
        else:
            formats = result.get('formats')
            if formats is not None:
                for frmt in formats:
                    if frmt.get('tbr'):

                        format_id = frmt['format_id']

                        if frmt.get('filesize'):
                            size = frmt['filesize']
                        elif frmt.get('filesize_approx'):
                            size = frmt['filesize_approx']
                        else:
                            size = 0

                        if frmt.get('height'):
                            height = frmt['height']
                            ext = frmt['ext']
                            fps = frmt['fps'] if frmt.get('fps') else ''
                            b_name = f"{height}p{fps}-{ext}"
                            if ext == 'mp4':
                                v_format = f"bv*[format_id={format_id}]+ba[ext=m4a]/b[height={height}]"
                            else:
                                v_format = f"bv*[format_id={format_id}]+ba/b[height={height}]"
                        elif frmt.get('video_ext') == 'none' and frmt.get('acodec') != 'none':
                            b_name = f"{frmt['acodec']}-{frmt['ext']}"
                            v_format = f"ba[format_id={format_id}]"
                        else:
                            continue

                        if b_name in formats_dict:
                            formats_dict[b_name][str(frmt['tbr'])] = [size, v_format]
                        else:
                            subformat = {str(frmt['tbr']): [size, v_format]}
                            formats_dict[b_name] = subformat

                for b_name, d_dict in formats_dict.items():
                    if len(d_dict) == 1:
                        tbr, v_list = list(d_dict.items())[0]
                        buttonName = f"{b_name} ({get_readable_file_size(v_list[0])})"
                        buttons.sbutton(buttonName, f"qu {msg_id} {b_name}|{tbr}")
                    else:
                        buttons.sbutton(b_name, f"qu {msg_id} dict {b_name}")
            buttons.sbutton("MP3", f"qu {msg_id} mp3")
            buttons.sbutton("Best Video", f"qu {msg_id} {best_video}")
            buttons.sbutton("Best Audio", f"qu {msg_id} {best_audio}")
            buttons.sbutton("Cancel", f"qu {msg_id} cancel")
            YTBUTTONS = buttons.build_menu(2)
            listener_dict[msg_id] = [listener, user_id, link, name, YTBUTTONS, opt, formats_dict]
            bmsg = sendMarkup('Choose Video Quality:', bot, message, YTBUTTONS)

        Thread(target=_auto_cancel, args=(bmsg, msg_id)).start()

    if multi > 1:
        sleep(4)
        nextmsg = type('nextmsg', (object, ), {'chat_id': message.chat_id, 'message_id': message.reply_to_message.message_id + 1})
        ymsg = mssg.split(maxsplit=mi+1)
        ymsg[mi] = f"{multi - 1}"
        nextmsg = sendMessage(" ".join(ymsg), bot, nextmsg)
        nextmsg.from_user.id = message.from_user.id
        sleep(4)
        Thread(target=_ytdl, args=(bot, nextmsg, isZip, isLeech)).start()

def _qual_subbuttons(task_id, b_name, msg):
    buttons = ButtonMaker()
    task_info = listener_dict[task_id]
    formats_dict = task_info[6]
    for tbr, d_data in formats_dict[b_name].items():
        buttonName = f"{tbr}K ({get_readable_file_size(d_data[0])})"
        buttons.sbutton(buttonName, f"qu {task_id} {b_name}|{tbr}")
    buttons.sbutton("Back", f"qu {task_id} back")
    buttons.sbutton("Cancel", f"qu {task_id} cancel")
    SUBBUTTONS = buttons.build_menu(2)
    editMessage(f"Choose Bit rate for <b>{b_name}</b>:", msg, SUBBUTTONS)

def _mp3_subbuttons(task_id, msg, playlist=False):
    buttons = ButtonMaker()
    audio_qualities = [64, 128, 320]
    for q in audio_qualities:
        if playlist:
            i = 's'
            audio_format = f"ba/b-{q} t"
        else:
            i = ''
            audio_format = f"ba/b-{q}"
        buttons.sbutton(f"{q}K-mp3", f"qu {task_id} {audio_format}")
    buttons.sbutton("Back", f"qu {task_id} back")
    buttons.sbutton("Cancel", f"qu {task_id} cancel")
    SUBBUTTONS = buttons.build_menu(2)
    editMessage(f"Choose Audio{i} Bitrate:", msg, SUBBUTTONS)

def select_format(update, context):
    query = update.callback_query
    user_id = query.from_user.id
    data = query.data
    msg = query.message
    data = data.split(" ")
    task_id = int(data[1])
    try:
        task_info = listener_dict[task_id]
    except:
        return editMessage("This is an old task", msg)
    uid = task_info[1]
    if user_id != uid and not CustomFilters.owner_query(user_id):
        return query.answer(text="This task is not for you!", show_alert=True)
    elif data[2] == "dict":
        query.answer()
        b_name = data[3]
        _qual_subbuttons(task_id, b_name, msg)
        return
    elif data[2] == "back":
        query.answer()
        return editMessage('Choose Video Quality:', msg, task_info[4])
    elif data[2] == "mp3":
        query.answer()
        playlist = len(data) == 4
        _mp3_subbuttons(task_id, msg, playlist)
        return
    elif data[2] == "cancel":
        query.answer()
        editMessage('Task has been cancelled.', msg)
    else:
        query.answer()
        listener = task_info[0]
        link = task_info[2]
        name = task_info[3]
        opt = task_info[5]
        qual = data[2]
        if len(data) == 4:
            playlist = True
            if '|' in qual:
                qual = task_info[6][qual]
        else:
            playlist = False
            if '|' in qual:
                b_name, tbr = qual.split('|')
                qual = task_info[6][b_name][tbr][1]
        ydl = YoutubeDLHelper(listener)
        Thread(target=ydl.add_download, args=(link, f'{DOWNLOAD_DIR}{task_id}', name, qual, playlist, opt)).start()
        query.message.delete()
    del listener_dict[task_id]

def _auto_cancel(msg, task_id):
    sleep(120)
    try:
        del listener_dict[task_id]
        editMessage('Timed out! Task has been cancelled.', msg)
    except:
        pass

def ytdl(update, context):
    _ytdl(context.bot, update.message)

def ytdlZip(update, context):
    _ytdl(context.bot, update.message, True)

def ytdlleech(update, context):
    _ytdl(context.bot, update.message, isLeech=True)

def ytdlZipleech(update, context):
    _ytdl(context.bot, update.message, True, True)


ytdl_handler = CommandHandler(BotCommands.YtdlCommand, ytdl,
                              filters=CustomFilters.authorized_chat | CustomFilters.authorized_user, run_async=True)
ytdl_zip_handler = CommandHandler(BotCommands.YtdlZipCommand, ytdlZip,
                              filters=CustomFilters.authorized_chat | CustomFilters.authorized_user, run_async=True)
ytdl_leech_handler = CommandHandler(BotCommands.YtdlLeechCommand, ytdlleech,
                              filters=CustomFilters.authorized_chat | CustomFilters.authorized_user, run_async=True)
ytdl_zip_leech_handler = CommandHandler(BotCommands.YtdlZipLeechCommand, ytdlZipleech,
                              filters=CustomFilters.authorized_chat | CustomFilters.authorized_user, run_async=True)
quality_handler = CallbackQueryHandler(select_format, pattern="qu", run_async=True)

dispatcher.add_handler(ytdl_handler)
dispatcher.add_handler(ytdl_zip_handler)
dispatcher.add_handler(ytdl_leech_handler)
dispatcher.add_handler(ytdl_zip_leech_handler)
dispatcher.add_handler(quality_handler)
