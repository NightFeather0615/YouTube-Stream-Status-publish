import os
import json
import requests
import datetime
import discord
from discord.ext import commands, tasks
from dotenv import *
from Naked.toolshed.shell import muterun_js

client = commands.Bot(command_prefix='>>', intents=discord.Intents.all())
client.remove_command("help")
load_dotenv()
google_api_key = os.getenv("GOOGLE_API_KEY")
channel_id = os.getenv("YOUTUBE_CHANNEL_ID")
channel_title = ""
guild_id = os.getenv("GUILD_ID")
upcoming_notify_message = os.getenv("UPCOMING_NOTIFY_MESSAGE")
live_notify_message = os.getenv("LIVE_NOTIFY_MESSAGE")
notify_channel_id = os.getenv("NOTIFY_CHANNEL_ID")
notify_role_id = os.getenv("NOTIFY_ROLE_ID")

@tasks.loop(minutes=1)
async def track_new_stream():
  response = muterun_js('js_script/index.js', channel_id)
  if response.exitcode == 0:
    return_data = response.stdout.decode("utf-8").replace('\n', "")
    if return_data != "false":
        stream_status.start(return_data)
        track_new_stream.cancel()
  else:
    print("Error: 確認串流狀態時發生了未知的錯誤，請確認是否有安裝Node.js及其所需模組")

@tasks.loop(minutes=1)
async def stream_status(video_url):
  global channel_title
  video_id = video_url.split("/watch?v=")[1]
  stream_data = requests.get(f"https://www.googleapis.com/youtube/v3/videos?id={video_id}&part=snippet,liveStreamingDetails&key={google_api_key}")
  stream_data = stream_data.json()
  video_title = stream_data['items'][0]['snippet'].get('title')
  guild = await client.fetch_guild(guild_id)
  member = await guild.fetch_member(client.user.id)
  notify_channel = await client.fetch_channel(notify_channel_id)
  actual_start_time = stream_data['items'][0]['liveStreamingDetails'].get("actualStartTime")
  actual_end_time = stream_data['items'][0]['liveStreamingDetails'].get("actualEndTime")
  live_broadcast_content = stream_data['items'][0]['snippet'].get("liveBroadcastContent")
  concurrent_viewers = stream_data['items'][0]['liveStreamingDetails'].get("concurrentViewers")
  if actual_start_time != None:
    actual_start_time = datetime.datetime.strptime(actual_start_time, "%Y-%m-%dT%H:%M:%SZ")
  scheduled_start_time = datetime.datetime.strptime(stream_data['items'][0]['liveStreamingDetails'].get("scheduledStartTime"), "%Y-%m-%dT%H:%M:%SZ")
  active_live_chat_id = stream_data['items'][0]['liveStreamingDetails'].get("activeLiveChatId")
  with open('catch.json', 'r', encoding='utf8') as f:
    catch_data = json.load(f)
  if live_broadcast_content == "upcoming":
    await client.change_presence(status=discord.Status.online, activity=discord.Streaming(name=video_title, url=f"https://www.youtube.com/watch?v={video_id}"))
    await member.edit(nick = f"🟠 待機")
    if catch_data["upcoming_catch"] != video_id:
      catch_data["upcoming_catch"] = video_id
      if not "actual_start_timestamp" in upcoming_notify_message:
        msg = upcoming_notify_message.replace("$scheduled_start_timestamp$", str(round(scheduled_start_time.timestamp()) + 28800))
        msg = msg.replace("$role_tag$", f"<@&{notify_role_id}>")
        msg = msg.replace("$role_id$", notify_role_id)
        msg = msg.replace("$channel_title$", channel_title)
        msg = msg.replace("$video_url$", video_url)
        msg = msg.replace("$video_title$", video_title)
        await notify_channel.send(content=msg)
      else:
        print('Error: 無法取得無效參數"actualStartTime"，尚未開始的串流不包含此參數')
      with open('catch.json', 'w') as f:
        json.dump(catch_data, f, indent=4)
  elif live_broadcast_content == "live" and actual_end_time == None:
    await client.change_presence(status=discord.Status.online, activity=discord.Streaming(name=video_title, url=f"https://www.youtube.com/watch?v={video_id}"))
    await member.edit(nick = f"🔴 直播中")
    if catch_data["live_catch"] != video_id:
      catch_data["live_catch"] = video_id
      msg = live_notify_message.replace("$scheduled_start_timestamp$", str(round(scheduled_start_time.timestamp()) + 28800))
      msg = msg.replace("$actual_start_timestamp$", str(round(actual_start_time.timestamp()) + 28800))
      msg = msg.replace("$role_tag$", f"<@&{notify_role_id}>")
      msg = msg.replace("$role_id$", notify_role_id)
      msg = msg.replace("$channel_title$", channel_title)
      msg = msg.replace("$video_url$", video_url)
      msg = msg.replace("$video_title$", video_title)
      await notify_channel.send(content=msg)
      with open('catch.json', 'w') as f:
        json.dump(catch_data, f, indent=4)
  elif live_broadcast_content == "live" and actual_end_time != None:
    await client.change_presence(status=discord.Status.online)
    await member.edit(nick = f"⚫ 無活動")
    track_new_stream.start()
    stream_status.cancel()

@tasks.loop(hours=24)
async def sync_channel_data():
  global channel_title
  channel_data = requests.get(f"https://www.googleapis.com/youtube/v3/channels?part=snippet&id={channel_id}&key={google_api_key}")
  channel_data = channel_data.json()
  pfp_url = channel_data['items'][0]['snippet']['thumbnails']['high']['url']
  channel_title = channel_data['items'][0]['snippet'].get("title")
  img_data = requests.get(pfp_url).content
  with open('channel_avatar.jpg', 'wb') as handler:
    handler.write(img_data)
  with open('channel_avatar.jpg', 'rb') as f:
    await client.user.edit(avatar=f.read())

@client.event
async def on_ready():
  print('<Logged in as {0.user}>'.format(client))
  track_new_stream.start()
  sync_channel_data.start()

client.run(os.getenv("TOKEN"))