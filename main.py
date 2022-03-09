import os
import json
import datetime
import discord
import aiohttp
import sys
import logging
from discord.ext import commands, tasks
from dotenv import *
from Naked.toolshed.shell import muterun_js


client = commands.AutoShardedBot(command_prefix='>>',
                      intents=discord.Intents.all())

logging.basicConfig(level=logging.INFO,
                    format='[%(asctime)s] [%(levelname)s] %(message)s',
                    datefmt='%Y/%m/%d %I:%M:%S')

client.remove_command("help")
load_dotenv()
google_api_key = os.getenv("GOOGLE_API_KEY")
utc_timezone = int(os.getenv("UTC_TIMEZONE"))
channel_id = os.getenv("YOUTUBE_CHANNEL_ID")
channel_title = ""
guild_id = os.getenv("GUILD_ID")
upcoming_notify_message = os.getenv("UPCOMING_NOTIFY_MESSAGE")
live_notify_message = os.getenv("LIVE_NOTIFY_MESSAGE")
end_notify_message = os.getenv("END_NOTIFY_MESSAGE")
notify_channel_id = os.getenv("NOTIFY_CHANNEL_ID")
notify_role_id = os.getenv("NOTIFY_ROLE_ID")
refresh_index = 0

@client.event
async def on_error(event):
  error = sys.exc_info()
  logging.error(f"Event {event} raised {error[0].__name__}: {error[1]}")

@client.event
async def on_ready():
  logging.info(f"Logged in as {client.user}")
  logging.info(f"Google API token: {google_api_key}")
  logging.info(f"Start track channel, ID: {channel_id}")
  sync_channel_avatar.start()
  track_new_stream.start()

@client.event
async def on_resumed():
  logging.info(f"Connection resumed")
  sync_channel_avatar.start()
  track_new_stream.start()

@client.event
async def on_connect():
  logging.info("Connected to Discord")

@client.event
async def on_disconnect():
  logging.warning("Disconnected to Discord")
  sync_channel_avatar.cancel()
  track_new_stream.cancel()

async def process_notify_message(notify_type, video_id):
  async with aiohttp.ClientSession() as session:
    async with session.get(f"https://www.googleapis.com/youtube/v3/videos?id={video_id}&part=snippet,liveStreamingDetails&key={google_api_key}") as stream_raw_data:
      stream_data = await stream_raw_data.json()
      video_title = stream_data['items'][0]['snippet'].get('title')
      video_url = f"https://www.youtube.com/watch?v={video_id}"
      actual_start_time = stream_data['items'][0]['liveStreamingDetails'].get("actualStartTime")
      actual_end_time = stream_data['items'][0]['liveStreamingDetails'].get("actualEndTime")
      scheduled_start_time = datetime.datetime.strptime(stream_data['items'][0]['liveStreamingDetails'].get("scheduledStartTime"), "%Y-%m-%dT%H:%M:%SZ")
      elapsed_time = None
      if actual_start_time != None:
        actual_start_time = datetime.datetime.strptime(actual_start_time, "%Y-%m-%dT%H:%M:%SZ")
      if actual_end_time != None:
        actual_end_time = datetime.datetime.strptime(actual_end_time, "%Y-%m-%dT%H:%M:%SZ")
      if actual_start_time != None and actual_end_time != None:
        elapsed_time = datetime.timedelta(seconds=round(actual_end_time.timestamp()) - round(actual_start_time.timestamp()))
      if notify_type == "upcoming":
        if not ("$[actual_start_timestamp]$" or "$[actual_end_timestamp]$" or "$[elapsed_time]$") in upcoming_notify_message:
          msg = upcoming_notify_message.replace("$[scheduled_start_timestamp]$", str(round(scheduled_start_time.timestamp()) + (utc_timezone * 3600)))
          msg = msg.replace("$[role_tag]$", f"<@&{notify_role_id}>")
          msg = msg.replace("$[role_id]$", notify_role_id)
          msg = msg.replace("$[channel_title]$", channel_title)
          msg = msg.replace("$[video_url]$", video_url)
          msg = msg.replace("$[video_title]$", video_title)
          return msg
        else:
          logging.error("自訂通知包含無效參數，尚未開始的串流不包含所要求的參數")
          return None
      elif notify_type == "live":
        if not ("$[actual_end_timestamp]$" or "$[elapsed_time]$") in live_notify_message:
          msg = live_notify_message.replace("$[scheduled_start_timestamp]$", str(round(scheduled_start_time.timestamp()) + (utc_timezone * 3600)))
          msg = msg.replace("$[actual_start_timestamp]$", str(round(actual_start_time.timestamp()) + (utc_timezone * 3600)))
          msg = msg.replace("$[role_tag]$", f"<@&{notify_role_id}>")
          msg = msg.replace("$[role_id]$", notify_role_id)
          msg = msg.replace("$[channel_title]$", channel_title)
          msg = msg.replace("$[video_url]$", video_url)
          msg = msg.replace("$[video_title]$", video_title)
          return msg
        else:
          logging.error("自訂通知包含無效參數，進行中的串流不包含所要求的參數")
          return None
      elif notify_type == "end":
        msg = end_notify_message.replace("$[scheduled_start_timestamp]$", str(round(scheduled_start_time.timestamp()) + (utc_timezone * 3600)))
        msg = msg.replace("$[actual_start_timestamp]$", str(round(actual_start_time.timestamp()) + (utc_timezone * 3600)))
        msg = msg.replace("$[actual_end_timestamp]$", str(round(actual_end_time.timestamp()) + (utc_timezone * 3600)))
        msg = msg.replace("$[elapsed_time]$", str(elapsed_time))
        msg = msg.replace("$[role_tag]$", f"<@&{notify_role_id}>")
        msg = msg.replace("$[role_id]$", notify_role_id)
        msg = msg.replace("$[channel_title]$", channel_title)
        msg = msg.replace("$[video_url]$", video_url)
        msg = msg.replace("$[video_title]$", video_title)
        return msg
      else:
        logging.error("無效的訊息類別")
        return None

last_stream_id = None

@tasks.loop(minutes=1)
async def track_new_stream():
  global last_stream_id
  response = muterun_js('js_script/index.js', channel_id)
  if response.exitcode == 0:
    response_data = response.stdout.decode("utf-8").replace('\n', "")
    if response_data != "false":
      video_id = response_data.split("/watch?v=")[1]
      if last_stream_id != video_id:
        last_stream_id = video_id
        logging.info(f"Detected new stream")
        logging.info(f"Start track stream status, ID: {video_id}")
      track_stream_status.start(response_data)
      track_new_stream.cancel()
  else:
    logging.error(f"Unable to get stream info")

@tasks.loop(minutes=1)
async def track_stream_status(response_data):
  global channel_title
  global refresh_index
  refresh_index += 1
  guild = await client.fetch_guild(guild_id)
  member = await guild.fetch_member(client.user.id)
  notify_channel = await client.fetch_channel(notify_channel_id)
  video_id = response_data.split("/watch?v=")[1]
  async with aiohttp.ClientSession() as session:
    async with session.get(f"https://www.googleapis.com/youtube/v3/videos?id={video_id}&part=snippet,liveStreamingDetails&key={google_api_key}") as stream_raw_data:
      stream_data = await stream_raw_data.json()
      live_broadcast_content = stream_data['items'][0]['snippet'].get("liveBroadcastContent")
      video_title = stream_data['items'][0]['snippet'].get('title')
      scheduled_start_time = datetime.datetime.strptime(stream_data['items'][0]['liveStreamingDetails'].get("scheduledStartTime"), "%Y-%m-%dT%H:%M:%SZ")
      with open('catch.json', 'r', encoding='utf8') as f:
        catch_data = json.load(f)
      if refresh_index >= 5:
        refresh_index = 0
        track_new_stream.start()
        track_stream_status.cancel()
      else:
        if live_broadcast_content == "upcoming" and not ((scheduled_start_time - datetime.datetime.now()).days <= 14):
          await client.change_presence(status=discord.Status.online, activity=discord.Streaming(name=video_title, url=f"https://www.youtube.com/watch?v={video_id}"))
          await member.edit(nick = f"🟠 待機中")
          if catch_data["upcoming_catch"] != video_id:
            logging.info(f"Channel stream status updated: Upcoming")

            msg = await process_notify_message("upcoming", video_id)
            if msg != None:
              await notify_channel.send(content=msg)

            with open('catch.json', 'w') as f:
              catch_data["upcoming_catch"] = video_id
              json.dump(catch_data, f, indent=4)

        elif live_broadcast_content == "live":
          await client.change_presence(status=discord.Status.online, activity=discord.Streaming(name=video_title, url=f"https://www.youtube.com/watch?v={video_id}"))
          await member.edit(nick = f"🔴 直播中")
          if catch_data["live_catch"] != video_id:
            logging.info(f"Channel stream status updated: Streaming")
            
            msg = await process_notify_message("live", video_id)
            if msg != None:
              await notify_channel.send(content=msg)
            with open('catch.json', 'w') as f:
              catch_data["live_catch"] = video_id
              json.dump(catch_data, f, indent=4)

        elif live_broadcast_content == "none" or (live_broadcast_content == "upcoming" and (scheduled_start_time - datetime.datetime.now()).days <= 14):
          await client.change_presence(status=discord.Status.online)
          await member.edit(nick = f"⚫ 無活動")
          if catch_data["end_catch"] != video_id:
            logging.info(f"Channel stream status updated: None")
            logging.info(f"Start track new stream")
            
            msg = await process_notify_message("end", video_id)
            if msg != None:
              await notify_channel.send(content=msg)

            with open('catch.json', 'w') as f:
              catch_data["end_catch"] = video_id
              json.dump(catch_data, f, indent=4)

          track_new_stream.start()
          track_stream_status.cancel()

@tasks.loop(hours=24)
async def sync_channel_avatar():
  global channel_title
  logging.info(f"Sync channel avatar")
  async with aiohttp.ClientSession() as session:
    async with session.get(f"https://www.googleapis.com/youtube/v3/channels?part=snippet&id={channel_id}&key={google_api_key}") as channel_raw_data:
      channel_data = await channel_raw_data.json()
      pfp_url = channel_data['items'][0]['snippet']['thumbnails']['high']['url']
      channel_title = channel_data['items'][0]['snippet'].get("title")
      async with aiohttp.ClientSession() as session:
        async with session.get(pfp_url) as img_raw_data:
          img = await img_raw_data.content.read()
      with open('channel_avatar.jpg', 'wb') as handler:
        handler.write(img)
      with open('channel_avatar.jpg', 'rb') as f:
        await client.user.edit(avatar=f.read())

client.run(os.getenv("TOKEN"))
