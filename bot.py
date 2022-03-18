from logging import INFO
import random
from discord.ext import commands
import discord
from discord import FFmpegPCMAudio
from youtube_dl import YoutubeDL
import yaml
import spotipy
from spotipy.oauth2 import SpotifyClientCredentials
import asyncio

with open("/app/conf.yml", 'r') as f:
    conf = yaml.safe_load(f.read())

spotify = spotipy.Spotify(client_credentials_manager=SpotifyClientCredentials(conf['spot_client_id'],conf['spot_secret']))

TOKEN = conf['discord_token']

description = '''jaguar's bot'''
bot = commands.Bot(command_prefix='`', description=description)

YDL_OPTIONS = {'verbose': True, 'format': 'bestaudio', 'noplaylist':'True', 'username':conf['username_yt'], 'password':conf['password_yt'], 'cookiefile':'cookies.txt', 'force-ipv4':True, 'cachedir':False}
YDL_OPTIONS_SC = {'forcejson':True, 'nocheckcertificate':True, 'verbose': True, 'simulate':True, 'username':conf['username_sc'], 'password':conf['password_sc'], 'cookiefile':'cookies.txt', 'force-ipv4':True, 'cachedir':False}
FFMPEG_OPTIONS = {'before_options': '-reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 5 -re', 'options': '-vn'}
QUEUE = {}
NOW_PLAYING = {}
LOOP = {}


@bot.event
async def on_ready():
    print('Logged in as')
    print(bot.user.name)
    print(bot.user.id)
    print('------')

@bot.event
async def on_command_error(ctx, error):
    if isinstance(error, commands.CommandNotFound):
        msg = "Whatever you're saying, it's not penguin talk :/"
        await send_message(ctx, discord.Color.red(), 'Error', msg)

@bot.command()
async def debug(ctx):
    """for debugging and testing purposes"""
    for id in QUEUE:
        print(bot.get_guild(id), ':', len(QUEUE[id]))
    print(LOOP)
    print(NOW_PLAYING)
    print(ctx.message.guild.voice_client)

@bot.command()
async def diceroll(ctx):
    """rolls a 6-sided dice, always 6"""
    await send_message(ctx, discord.Color.teal(), 'Dice Roll', 'Six!')

@bot.command()
async def coinflip(ctx):
    """flips a coin, always heads"""
    await send_message(ctx, discord.Color.teal(), 'Coin Flip', 'Heads!')

@bot.command()
async def p(ctx, *args):
    """alias for <play> command"""
    await play(ctx, *args)

@bot.command()
async def play(ctx, *args):
    """plays youtube or spotify via url"""
    global QUEUE
    await connect(ctx)
    if ctx.guild.id not in NOW_PLAYING:
        NOW_PLAYING[ctx.guild.id] = ''
    if ctx.guild.id not in LOOP:
        LOOP[ctx.guild.id] = ''
    if not ctx.message.guild.voice_client.is_playing():
        if 'youtube.com/watch' in args[0] or 'youtu.be' in args[0]:
            print('1')
            await play_youtube(args[0], ctx)
        elif 'open.spotify.com/track' in args[0]:
            print('2')
            await play_spotify(args[0], ctx)
        elif 'open.spotify.com/album' in args[0] or 'open.spotify.com/playlist' in args[0]:
            await spotify_process(args[0], ctx)
        elif 'soundcloud.com' in args[0]:
            await play_soundcloud(args[0], ctx)
        else:
            print('3')
            words = ' '.join(args)
            await send_message(ctx, discord.Color.teal(), 'Searching', f'Searching for: {words}')
            await play_youtube(words, ctx, True)
    elif 'open.spotify.com/album' in args[0]:
        await spotify_process(args[0], ctx)
    elif 'open.spotify.com/playlist' in args[0]:
        await spotify_process(args[0], ctx)
    else:
        await spotify_process(args,ctx)

@bot.command()
async def pn(ctx, *args):
    """ Alias for playnow """
    await playnow(ctx, *args)

@bot.command()
async def playnow(ctx, *args):
    """ Puts song first in queue"""
    if 'open.spotify.com/playlist' in args[0] or 'open.spotify.com/album' in args[0]:
        await send_message(ctx, discord.Color.red(), 'Error', "Yeah I can't do that yet :( \n I can only put single tracks in queue for now!")
    else:
        await send_message(ctx, discord.Color.teal(), 'Adding to Queue', 'Adding to first in queue...')
        await add_to_queue(' '.join(args), ctx, True)

@bot.command()
async def shuffle(ctx):
    """ Shuffles the entire queue """
    try:
        random.shuffle(QUEUE[ctx.guild.id])
        await send_message(ctx, discord.Color.teal(), 'Shuffle', 'Queue has been shuffled/randomized')
    except KeyError:
        await send_message(ctx, discord.Color.red(), 'Error', "Maybe get an actual queue going?")
    except:
        await send_message(ctx, discord.Color.red(), 'Error', "??? Something went wrong.")


async def play_song(URL, song_name, ctx):
    if LOOP[ctx.guild.id] == True:
        await send_message(ctx, discord.Color.teal(), 'Playing (LOOP)', f"Use command 'loopoff' to turn off looping")
    else:
        await send_message(ctx, discord.Color.teal(), 'Playing', f"Now playing: {song_name}")
    NOW_PLAYING[ctx.guild.id] = song_name
    print(ctx.guild.name)
    try:
        ctx.message.guild.voice_client.play(FFmpegPCMAudio(URL, **FFMPEG_OPTIONS, executable='C:/ffmpeg/bin/ffmpeg.exe'), after=lambda e: asyncio.run_coroutine_threadsafe(after_song(ctx, URL, song_name, LOOP[ctx.guild.id]), bot.loop))
        ctx.message.guild.voice_client.is_playing()
    except Exception as err:
        await error_handle(song_name, err, ctx)

async def after_song(ctx, URL, song_name = '', loop = False, skip = False):
    global QUEUE
    if loop == True and skip == False:
        await play_song(URL, song_name, ctx)
    elif ctx.guild.id not in QUEUE:
        pass
    else:
        if len(QUEUE[ctx.guild.id]) > 0:
            guild_queue = QUEUE[ctx.guild.id]
            next_song = guild_queue.pop(0)
            if 'youtube.com/watch' in next_song:
                await play_youtube(next_song, ctx)
            elif 'open.spotify.com' in next_song:
                await play_spotify(next_song, ctx)
            else:
                await play_youtube(next_song, ctx, True)
        else:
            try:
                NOW_PLAYING[ctx.guild.id] = ''
            except Exception as err:
                print('----------NOW PLAYING ERROR---------', err)

async def play_spotify(url, ctx):
    print('============Playing Spotify============')
    print(url)
    track = spotify.track(url)
    track_name = track['name']
    track_artist = track['artists'][0]['name']
    with YoutubeDL(YDL_OPTIONS) as ydl:
        try:
            info = ydl.extract_info(f"ytsearch:{track_name} {track_artist}", download=False)
        except Exception as err:
            await error_handle(url, err, ctx)
            return
    URL = info['entries'][0]['formats'][3]['url']
    song_name = info['entries'][0]['title']
    await play_song(URL, song_name, ctx)

async def play_youtube(url, ctx, search = False):
    global QUEUE
    with YoutubeDL(YDL_OPTIONS) as ydl:
        if search:
            print('============Playing searching============')
            print(url)
            try:
                info = ydl.extract_info(f"ytsearch:{url}", download=False)
            except Exception as err:
                await error_handle(url, err, ctx)
                return
            URL = info['entries'][0]['formats'][3]['url']
            song_name = info['entries'][0]['title']
        elif not search:
            print('============Playing Youtube link============')
            print(url)
            try:
                info = ydl.extract_info(url, download=False)
            except Exception as err:
                await error_handle(url, err, ctx)
                return
            URL = info['formats'][0]['url']
            song_name = info['title']
    await play_song(URL, song_name, ctx)

async def play_soundcloud(url, ctx):
    global QUEUE
    with YoutubeDL(YDL_OPTIONS_SC) as ydl:
        print('============Playing Soundcloud link============')
        print(url)
        try:
            info = ydl.extract_info(url)
        except Exception as err:
            await error_handle(url, err, ctx)
            print('test')
            return
        URL = info['formats'][2]['url']
        song_name = info['title']
        print(song_name)
        print(URL)
        print('test')
    await play_song(URL, song_name, ctx)        

async def error_handle(url, err, ctx):
    print('error_handle function')
    embed = discord.Embed(color=discord.Color.red())
    if "Sign in to confirm your age" in str(err):
        message = 'This link is age restricted :( Skipping to next song in queue if any...'
    elif "Video unavailable" in str(err):
        message = 'This link is unavailable :( Skipping to next song in queue if any...'
    else:
        message = 'Something when wrong... :( Skipping to next song in queue if any...' 
        print('======== PLAY_YOUTUBE ERROR ======', err)
    embed.add_field(name='Error', value=f"{message}", inline=True)
    embed.add_field(name='Suspected Link', value=url, inline=True)
    await ctx.send(embed=embed)
    await skip(ctx, True)
    return

async def spotify_process(url, ctx):
    if 'open.spotify.com/playlist' in url:
        count = 0
        for x in spotify.playlist_tracks(url)['items']:
            track_url = x['track']['external_urls']['spotify']
            if not ctx.message.guild.voice_client.is_playing():
                await play_spotify(track_url, ctx)
            else:
                await add_to_queue(track_url, ctx)
                count += 1
        await send_message(ctx, discord.Color.teal(), 'Adding to Queue', f"Adding {count} songs, \n Total songs in queue: {len(QUEUE[ctx.guild.id])}")
    elif 'open.spotify.com/album' in url:
        count = 0
        for x in spotify.album_tracks(url)['items']:
            track_url = x['external_urls']['spotify']
            if not ctx.message.guild.voice_client.is_playing():
                await play_spotify(track_url, ctx)
            else:
                await add_to_queue(track_url, ctx)
                count += 1
        await send_message(ctx, discord.Color.teal(), 'Adding to Queue', f"Adding {count} songs, \n Total songs in queue: {len(QUEUE[ctx.guild.id])}")
    else:
        search = ' '.join(url)
        await send_message(ctx, discord.Color.teal(), 'Adding to Queue', "Adding to queue...")
        await add_to_queue(search, ctx)

async def add_to_queue(url, ctx, first = False):
    global QUEUE
    if ctx.guild.id not in QUEUE:
        QUEUE[ctx.guild.id] = [url]
    elif ctx.guild.id in QUEUE:
        if first == True:
            QUEUE[ctx.guild.id].insert(0, url)
        else:
            QUEUE[ctx.guild.id].append(url)

async def send_message(ctx, msg_color, title, body):
    embed = discord.Embed(color=msg_color)
    embed.add_field(name=title, value=body, inline=True)
    await ctx.send(embed=embed)

@bot.command()
async def queue(ctx):
    """shows queue"""
    try:
        count = len(QUEUE[ctx.guild.id])
        if count == 0:
            await send_message(ctx, discord.Color.teal(), 'Queue', f"There are {count} songs in queue")
            return
        x = QUEUE[ctx.guild.id]
        if count == 1:
            msg = f"Here's the next song up next: \n {x[0]}"
        elif count == 2:
            msg = f"Here are the next 2 songs up next: \n {x[0]} \n {x[1]}"
        elif count == 3:
            msg = f"Here are the next 3 songs up next: \n {x[0]} \n {x[1]} \n {x[2]}"
        elif count == 4:
            msg = f"Here are the next 4 songs up next: \n {x[0]} \n {x[1]} \n {x[2]} \n {x[3]}"
        elif count >= 5:
            msg = f"Here are the next 5 songs up next: \n {x[0]} \n {x[1]} \n {x[2]} \n {x[3]} \n {x[4]} \n ..."
        await send_message(ctx, discord.Color.teal(), 'Queue', f"{msg} \n There are {count} songs in queue")
    except KeyError:
        await send_message(ctx, discord.Color.red(), 'Error', "Maybe get an actual queue going?")
    except:
        await send_message(ctx, discord.Color.red(), 'Error', f"Something went wrong, but there are {count} songs in queue")

@bot.command()
async def loop(ctx):
    """loop currently playing"""
    LOOP[ctx.guild.id] = True
    await send_message(ctx, discord.Color.teal(), 'Loop', 'Now looping')

@bot.command()
async def loopoff(ctx):
    """turn off loop"""
    LOOP[ctx.guild.id] = False
    await send_message(ctx, discord.Color.teal(), 'Loop', 'Looping turned off')

@bot.command()
async def q(ctx):
    """alias for queue"""
    await queue(ctx)

@bot.command()
async def nowplaying(ctx):
    """shows currently playing"""
    current = NOW_PLAYING[ctx.guild.id]
    await send_message(ctx, discord.Color.teal(), 'Currently Playing', current)

@bot.command()
async def np(ctx):
    """alias for nowplaying"""
    await nowplaying(ctx)

@bot.command()
async def clear(ctx):
    """clears queue"""
    global QUEUE
    try:
        QUEUE[ctx.guild.id] = []
        await send_message(ctx, discord.Color.teal(), 'Clear', "There's nothing in the sea now :(")
    except:
        await send_message(ctx, discord.Color.red(), 'Error', "??? Something went wrong")


@bot.command()
async def skip(ctx, err = False):
    """skips currently playing"""
    if not err:
        await send_message(ctx, discord.Color.teal(), 'Skip', "Skipping...")
        ctx.message.guild.voice_client.stop()
        if len(QUEUE[ctx.guild.id]) <= 0:
            await send_message(ctx, discord.Color.red(), 'Skip', "There aren't any fish in the sea!")
    elif err:
        ctx.message.guild.voice_client.stop()
        await after_song(ctx, skip = True)
    return 

@bot.command()
async def s(ctx, err = False):
    """alias for skip"""
    await skip(ctx, err)

@bot.command()
async def stop(ctx):
    """stops currently playing"""
    ctx.message.guild.voice_client.pause()
    return

@bot.command()
async def disconnect(ctx):
    """disconnects from current voice channel"""
    global QUEUE
    VC = ctx.message.guild.voice_client
    try:
        QUEUE[ctx.guild.id] = []
    except:
        print('disconnect try/except catch')
    await VC.disconnect(force=True)

@bot.command()
async def leave(ctx):
    """alias for disconnect"""
    await disconnect(ctx)


@bot.command()
async def connect(ctx):
    """connects to voice channel"""
    try:
        channel = ctx.author.voice.channel
        print(channel)
        await channel.connect()
        pengu = await ctx.guild.fetch_member(conf['bot_id'])
        await pengu.edit(deafen=True)
    except AttributeError as err:
        await send_message(ctx, discord.Color.red(), 'Error', "You need to be in a voice channel first!")
    except discord.errors.ClientException as err2:
        print(err2)



@bot.command()
async def league(ctx, arg):
    """plays league quips. currently supported: <ornn> <rammus> <jax> <gangplank> <panth> <sion> <nocturne> <tahm>
        <1> <2> <3> <4> <5> <spree> <rampage> <unstoppable> <dominating> <godlike> <legendary> <allyslain> <disconnect>
        <defeat> <shutdown> <slain>"""
    await connect(ctx)
    try:
        if arg == "rammus":
            ctx.message.guild.voice_client.play(FFmpegPCMAudio("./sounds/rammus-ok.mp3", executable='C:/ffmpeg/bin/ffmpeg.exe'))
        elif arg == "ornn":
            ctx.message.guild.voice_client.play(FFmpegPCMAudio("./sounds/ornn-ult.mp3", executable='C:/ffmpeg/bin/ffmpeg.exe'))
        elif arg == "jax":
            ctx.message.guild.voice_client.play(FFmpegPCMAudio("./sounds/jax-real-weapon.mp3", executable='C:/ffmpeg/bin/ffmpeg.exe'))
        elif arg == "gangplank":
            ctx.message.guild.voice_client.play(FFmpegPCMAudio("./sounds/gangplank-ult.mp3", executable='C:/ffmpeg/bin/ffmpeg.exe'))
        elif arg == "panth":
            ctx.message.guild.voice_client.play(FFmpegPCMAudio("./sounds/pantheon-ult.mp3", executable='C:/ffmpeg/bin/ffmpeg.exe'))
        elif arg == "sion":
            ctx.message.guild.voice_client.play(FFmpegPCMAudio("./sounds/sion-ult.mp3", executable='C:/ffmpeg/bin/ffmpeg.exe'))
        elif arg == "nocturne":
            ctx.message.guild.voice_client.play(FFmpegPCMAudio("./sounds/nocturne-ult.mp3", executable='C:/ffmpeg/bin/ffmpeg.exe'))
        elif arg == "tahm":
            ctx.message.guild.voice_client.play(FFmpegPCMAudio("./sounds/tahm-misery.mp3", executable='C:/ffmpeg/bin/ffmpeg.exe'))
        elif arg == "1":
            ctx.message.guild.voice_client.play(FFmpegPCMAudio("./sounds/league-kill-1.mp3", executable='C:/ffmpeg/bin/ffmpeg.exe'))
        elif arg == "2":
            ctx.message.guild.voice_client.play(FFmpegPCMAudio("./sounds/league-kill-2.mp3", executable='C:/ffmpeg/bin/ffmpeg.exe'))
        elif arg == "3":
            ctx.message.guild.voice_client.play(FFmpegPCMAudio("./sounds/league-kill-3.mp3", executable='C:/ffmpeg/bin/ffmpeg.exe'))
        elif arg == "4":
            ctx.message.guild.voice_client.play(FFmpegPCMAudio("./sounds/league-kill-4.mp3", executable='C:/ffmpeg/bin/ffmpeg.exe'))
        elif arg == "5":
            ctx.message.guild.voice_client.play(FFmpegPCMAudio("./sounds/league-kill-5.mp3", executable='C:/ffmpeg/bin/ffmpeg.exe'))
        elif arg == "spree":
            ctx.message.guild.voice_client.play(FFmpegPCMAudio("./sounds/league-spree-enemy.mp3", executable='C:/ffmpeg/bin/ffmpeg.exe'))
        elif arg == "rampage":
            ctx.message.guild.voice_client.play(FFmpegPCMAudio("./sounds/league-rampage.mp3", executable='C:/ffmpeg/bin/ffmpeg.exe'))
        elif arg == "unstoppable":
            ctx.message.guild.voice_client.play(FFmpegPCMAudio("./sounds/league-unstoppable-enemy.mp3", executable='C:/ffmpeg/bin/ffmpeg.exe'))
        elif arg == "dominating":
            ctx.message.guild.voice_client.play(FFmpegPCMAudio("./sounds/league-dominating-enemy.mp3", executable='C:/ffmpeg/bin/ffmpeg.exe'))
        elif arg == "godlike":
            ctx.message.guild.voice_client.play(FFmpegPCMAudio("./sounds/league-godlike-enemy.mp3", executable='C:/ffmpeg/bin/ffmpeg.exe'))
        elif arg == "legendary":
            ctx.message.guild.voice_client.play(FFmpegPCMAudio("./sounds/league-legendary-enemy.mp3", executable='C:/ffmpeg/bin/ffmpeg.exe'))
        elif arg == "allyslain":
            ctx.message.guild.voice_client.play(FFmpegPCMAudio("./sounds/league-ally-slain.mp3", executable='C:/ffmpeg/bin/ffmpeg.exe'))
        elif arg == "disconnected" or arg == "disconnect":
            ctx.message.guild.voice_client.play(FFmpegPCMAudio("./sounds/league-disconnected.mp3", executable='C:/ffmpeg/bin/ffmpeg.exe'))
        elif arg == "defeat":
            ctx.message.guild.voice_client.play(FFmpegPCMAudio("./sounds/league-defeat.mp3", executable='C:/ffmpeg/bin/ffmpeg.exe'))
        elif arg == "shutdown":
            ctx.message.guild.voice_client.play(FFmpegPCMAudio("./sounds/league-shutdown.mp3", executable='C:/ffmpeg/bin/ffmpeg.exe'))
        elif arg == "slain":
            ctx.message.guild.voice_client.play(FFmpegPCMAudio("./sounds/league-you-slain.mp3", executable='C:/ffmpeg/bin/ffmpeg.exe'))
        else:
            await send_message(ctx, discord.Color.red(), 'Error', "Whatever you're saying, it's not penguin talk :/")
    except:
        await send_message(ctx, discord.Color.red(), 'Error', "I'm already talking!")

@bot.command()
async def l(ctx, arg):
    """alias for league command"""
    await league(ctx, arg)

@bot.command()
async def fortnite(ctx, arg):
    """plays fortnite quips. currently supported: <down> <storm>"""
    await connect(ctx)
    try:
        if arg == "down":
            ctx.message.guild.voice_client.play(FFmpegPCMAudio("./sounds/fortnite-death.mp3", executable='C:/ffmpeg/bin/ffmpeg.exe'))
        elif arg == "storm":
            ctx.message.guild.voice_client.play(FFmpegPCMAudio("./sounds/fortnite-storm.mp3", executable='C:/ffmpeg/bin/ffmpeg.exe'))
        else:
            await send_message(ctx, discord.Color.red(), 'Error', "Whatever you're saying, it's not penguin talk :/")
    except:
        await send_message(ctx, discord.Color.red(), 'Error', "I'm already talking!")

@bot.command()
async def apex(ctx, arg):
    """plays apex quips. currently supported: <shield>"""
    await connect(ctx)
    try:
        if arg == "shield":
            ctx.message.guild.voice_client.play(FFmpegPCMAudio("./sounds/apex-shield.mp3", executable='C:/ffmpeg/bin/ffmpeg.exe'))
        else:
            await send_message(ctx, discord.Color.red(), 'Error', "Whatever you're saying, it's not penguin talk :/")
    except:
        await send_message(ctx, discord.Color.red(), 'Error', "I'm already talking!")

@bot.command()
async def warzone(ctx, arg):
    """plays warzone quips. currently supported: <down> <shield>"""
    await connect(ctx)
    try:
        if arg == "down":
            ctx.message.guild.voice_client.play(FFmpegPCMAudio("./sounds/warzone-down.mp3", executable='C:/ffmpeg/bin/ffmpeg.exe'))
        elif arg == "shield":
            ctx.message.guild.voice_client.play(FFmpegPCMAudio("./sounds/warzone-shield.mp3", executable='C:/ffmpeg/bin/ffmpeg.exe'))
        else:
            await send_message(ctx, discord.Color.red(), 'Error', "Whatever you're saying, it's not penguin talk :/")
    except:
        await send_message(ctx, discord.Color.red(), 'Error', "I'm already talking!")

@bot.command()
async def valorant(ctx, arg):
    """plays valorant quips. currently supported: <1> <2> <3> <4> <ace>"""
    await connect(ctx)
    try:
        if arg == "1":
            ctx.message.guild.voice_client.play(FFmpegPCMAudio("./sounds/valorant-kill-1.mp3", executable='C:/ffmpeg/bin/ffmpeg.exe'))
        elif arg == "2":
            ctx.message.guild.voice_client.play(FFmpegPCMAudio("./sounds/valorant-kill-2.mp3", executable='C:/ffmpeg/bin/ffmpeg.exe'))
        elif arg == "3":
            ctx.message.guild.voice_client.play(FFmpegPCMAudio("./sounds/valorant-kill-3.mp3", executable='C:/ffmpeg/bin/ffmpeg.exe'))
        elif arg == "4":
            ctx.message.guild.voice_client.play(FFmpegPCMAudio("./sounds/valorant-kill-4.mp3", executable='C:/ffmpeg/bin/ffmpeg.exe'))
        elif arg == "ace" or arg == "5":
            ctx.message.guild.voice_client.play(FFmpegPCMAudio("./sounds/valorant-kill-ace.mp3", executable='C:/ffmpeg/bin/ffmpeg.exe'))
        else:
            await send_message(ctx, discord.Color.red(), 'Error', "Whatever you're saying, it's not penguin talk :/")
    except:
        await send_message(ctx, discord.Color.red(), 'Error', "I'm already talking!")

@bot.command()
async def coc(ctx, arg):
    """plays clash of clans / clash royale quips. currently supported: <taunt> <start>"""
    await connect(ctx)
    try:
        if arg == "taunt":
            ctx.message.guild.voice_client.play(FFmpegPCMAudio("./sounds/coc-taunt.mp3", executable='C:/ffmpeg/bin/ffmpeg.exe'))
        elif arg == "start":
            ctx.message.guild.voice_client.play(FFmpegPCMAudio("./sounds/coc-start.mp3", executable='C:/ffmpeg/bin/ffmpeg.exe'))
        else:
            await send_message(ctx, discord.Color.red(), 'Error', "Whatever you're saying, it's not penguin talk :/")
    except:
        await send_message(ctx, discord.Color.red(), 'Error', "I'm already talking!")

@bot.command()
async def smash(ctx, arg):
    """plays smash bros quips. currently supported: <bat> <shield> <challenge>"""
    await connect(ctx)
    try:
        if arg == "bat":
            ctx.message.guild.voice_client.play(FFmpegPCMAudio("./sounds/smash-bat.mp3", executable='C:/ffmpeg/bin/ffmpeg.exe'))
        elif arg == "shield":
            ctx.message.guild.voice_client.play(FFmpegPCMAudio("./sounds/smash-shield.mp3", executable='C:/ffmpeg/bin/ffmpeg.exe'))
        elif arg == "challenge":
            ctx.message.guild.voice_client.play(FFmpegPCMAudio("./sounds/smash-challenger.mp3", executable='C:/ffmpeg/bin/ffmpeg.exe'))
        else:
            await send_message(ctx, discord.Color.red(), 'Error', "Whatever you're saying, it's not penguin talk :/")
    except:
        await send_message(ctx, discord.Color.red(), 'Error', "I'm already talking!")

@bot.command()
async def vine(ctx, arg):
    """plays vine quips. currently supported: <boom> <bruh>"""
    await connect(ctx)
    try:
        if arg == "boom":
            ctx.message.guild.voice_client.play(FFmpegPCMAudio("./sounds/vine-boom.mp3", executable='C:/ffmpeg/bin/ffmpeg.exe'))
        elif arg == "bruh":
            ctx.message.guild.voice_client.play(FFmpegPCMAudio("./sounds/vine-bruh.mp3", executable='C:/ffmpeg/bin/ffmpeg.exe'))
        else:
            await send_message(ctx, discord.Color.red(), 'Error', "Whatever you're saying, it's not penguin talk :/")
    except:
        await send_message(ctx, discord.Color.red(), 'Error', "I'm already talking!")

@bot.command()
async def fart(ctx):
    """plays between 4 different fart sounds"""
    x = random.randint(1, 4)
    await connect(ctx)
    try:
        ctx.message.guild.voice_client.play(FFmpegPCMAudio(f"./sounds/fart-{x}.mp3", executable='C:/ffmpeg/bin/ffmpeg.exe'))
    except:
        await send_message(ctx, discord.Color.red(), 'Error', "I'm already talking!")

@bot.command()
async def torf(ctx):
    """picks either true or false, always true"""
    await send_message(ctx, discord.Color.teal(), 'True of False', "True!")


bot.run(TOKEN)