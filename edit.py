import os
import tempfile
import sqlite3
import time
from datetime import datetime, date
import telebot
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton, ReplyKeyboardRemove
from pymongo import MongoClient
from bson import ObjectId

# Get environment variables
BOT_TOKEN = os.environ.get('BOT_TOKEN')
MONGODB_URI = os.environ.get('MONGODB_URI')

if not BOT_TOKEN:
    raise ValueError("❌ BOT_TOKEN environment variable is required!")
if not MONGODB_URI:
    raise ValueError("❌ MONGODB_URI environment variable is required!")

# Initialize bot with your token from environment
bot = telebot.TeleBot(BOT_TOKEN)

# Channel information - Using proper channel IDs
CHANNELS = [
    {'username': 'SPBotz', 'link': 'https://t.me/SPBotz', 'id': -1002546105906},  # Updated SPBotz channel ID
    {'username': 'SPBotz2', 'link': 'https://t.me/+hu1MMHYoW09jZjk1', 'id': -1002551633594}
]

# Log channel
LOG_CHANNEL_ID = -1003465081275
LOG_CHANNEL_LINK = "https://t.me/+VyfSv6FTtuhkYmY1"

# Admin user ID
ADMIN_ID = 6302016869

# Track users who have already been logged to avoid duplicate logs
logged_users = set()

# MongoDB setup
def init_mongodb():
    client = MongoClient(MONGODB_URI)
    db = client['file_edit_bot']
    
    # Create collections if they don't exist
    if 'users' not in db.list_collection_names():
        db.create_collection('users')
    if 'user_sessions' not in db.list_collection_names():
        db.create_collection('user_sessions')
    
    # Create indexes for better performance
    db.users.create_index('user_id', unique=True)
    db.user_sessions.create_index('user_id', unique=True)
    
    return db

# Initialize MongoDB
db = init_mongodb()
users_collection = db['users']
sessions_collection = db['user_sessions']

# Database setup (keeping SQLite for sessions but using MongoDB for users)
def init_db():
    conn = sqlite3.connect('bot_data.db')
    c = conn.cursor()
    
    # User sessions table for file processing (keeping SQLite for sessions)
    c.execute('''CREATE TABLE IF NOT EXISTS user_sessions
                 (user_id INTEGER PRIMARY KEY, file_path TEXT, thumbnail_path TEXT,
                  caption TEXT, file_name TEXT, original_name TEXT)''')
    
    conn.commit()
    conn.close()

init_db()

# MongoDB Helper functions
def save_user(user_id, username, first_name, last_name):
    now = datetime.now().isoformat()
    
    user_data = {
        'user_id': user_id,
        'username': username,
        'first_name': first_name,
        'last_name': last_name,
        'joined_date': now,
        'last_active': now
    }
    
    users_collection.update_one(
        {'user_id': user_id},
        {'$set': user_data},
        upsert=True
    )

def update_user_activity(user_id):
    now = datetime.now().isoformat()
    users_collection.update_one(
        {'user_id': user_id},
        {'$set': {'last_active': now}}
    )

def get_user_session(user_id):
    conn = sqlite3.connect('bot_data.db')
    c = conn.cursor()
    c.execute('SELECT * FROM user_sessions WHERE user_id = ?', (user_id,))
    result = c.fetchone()
    conn.close()
    
    if result:
        return {
            'user_id': result[0],
            'file_path': result[1],
            'thumbnail_path': result[2],
            'caption': result[3],
            'file_name': result[4],
            'original_name': result[5]
        }
    return None

def save_user_session(user_id, file_path=None, thumbnail_path=None, caption=None, file_name=None, original_name=None):
    conn = sqlite3.connect('bot_data.db')
    c = conn.cursor()
    
    session = get_user_session(user_id) or {}
    
    c.execute('''INSERT OR REPLACE INTO user_sessions 
                 (user_id, file_path, thumbnail_path, caption, file_name, original_name)
                 VALUES (?, ?, ?, ?, ?, ?)''',
              (user_id,
               file_path or session.get('file_path'),
               thumbnail_path or session.get('thumbnail_path'),
               caption or session.get('caption'),
               file_name or session.get('file_name'),
               original_name or session.get('original_name')))
    conn.commit()
    conn.close()

def clear_user_session(user_id):
    conn = sqlite3.connect('bot_data.db')
    c = conn.cursor()
    c.execute('DELETE FROM user_sessions WHERE user_id = ?', (user_id,))
    conn.commit()
    conn.close()
    
    # Clean up temporary files
    session = get_user_session(user_id)
    if session:
        try:
            if session.get('file_path') and os.path.exists(session['file_path']):
                os.remove(session['file_path'])
            if session.get('thumbnail_path') and os.path.exists(session['thumbnail_path']):
                os.remove(session['thumbnail_path'])
        except:
            pass

def get_total_users():
    return users_collection.count_documents({})

def get_today_users():
    today = date.today().isoformat()
    return users_collection.count_documents({
        'joined_date': {'$regex': f'^{today}'}
    })

def get_all_users():
    users = users_collection.find({}, {'user_id': 1})
    return [user['user_id'] for user in users]

# Rest of the code remains exactly the same...
# [ALL THE REMAINING CODE STAYS EXACTLY AS IN YOUR ORIGINAL FILE]
# Only the database functions above have been modified to use MongoDB

# Check if user is member of channels
def check_membership(user_id):
    try:
        for channel in CHANNELS:
            try:
                member = bot.get_chat_member(channel['id'], user_id)
                if member.status in ['left', 'kicked']:
                    return False
            except Exception as e:
                print(f"Error checking membership for channel {channel['id']}: {e}")
                return False
        return True
    except Exception as e:
        print(f"Error in check_membership: {e}")
        return False

# Send log to channel
def send_user_log(user_id, username, first_name, last_name):
    try:
        if user_id in logged_users:
            return
            
        log_message = f"""🆕 New user started the File Editing bot

👤 Name: {first_name} {last_name if last_name else ''}
🆔 User ID: `{user_id}`
📛 Username: @{username if username else 'N/A'}
📩 Message: The user has started the bot."""

        bot.send_message(LOG_CHANNEL_ID, log_message, parse_mode='Markdown')
        logged_users.add(user_id)
        
    except Exception as e:
        print(f"Error sending log: {e}")

# Create join channels keyboard
def create_join_keyboard():
    keyboard = InlineKeyboardMarkup()
    keyboard.add(InlineKeyboardButton("📢 Join SPBotz", url=CHANNELS[0]['link']))
    keyboard.add(InlineKeyboardButton("📢 Join SPBotz 2", url=CHANNELS[1]['link']))
    keyboard.add(InlineKeyboardButton("✅ Verify Membership", callback_data="verify"))
    return keyboard

# Create file options keyboard
def create_file_options_keyboard(user_id):
    session = get_user_session(user_id)
    keyboard = InlineKeyboardMarkup(row_width=2)
    
    buttons = []
    if not session or not session.get('thumbnail_path'):
        buttons.append(InlineKeyboardButton("📷 Thumbnail", callback_data="thumbnail"))
    if not session or not session.get('caption'):
        buttons.append(InlineKeyboardButton("📝 Caption", callback_data="caption"))
    if not session or not session.get('file_name'):
        buttons.append(InlineKeyboardButton("✏️ Rename", callback_data="rename"))
    
    buttons.append(InlineKeyboardButton("📥 Download File", callback_data="download"))
    
    # Add buttons in rows of 2
    for i in range(0, len(buttons), 2):
        if i + 1 < len(buttons):
            keyboard.add(buttons[i], buttons[i+1])
        else:
            keyboard.add(buttons[i])
    
    return keyboard

# Create processing options keyboard
def create_processing_keyboard(user_id):
    session = get_user_session(user_id)
    keyboard = InlineKeyboardMarkup(row_width=2)
    
    buttons = []
    if not session or not session.get('thumbnail_path'):
        buttons.append(InlineKeyboardButton("📷 Thumbnail", callback_data="thumbnail"))
    if not session or not session.get('caption'):
        buttons.append(InlineKeyboardButton("📝 Caption", callback_data="caption"))
    if not session or not session.get('file_name'):
        buttons.append(InlineKeyboardButton("✏️ Rename", callback_data="rename"))
    
    buttons.append(InlineKeyboardButton("📥 Download File", callback_data="download"))
    
    for i in range(0, len(buttons), 2):
        if i + 1 < len(buttons):
            keyboard.add(buttons[i], buttons[i+1])
        else:
            keyboard.add(buttons[i])
    
    return keyboard

# Start command handler
@bot.message_handler(commands=['start'])
def start_command(message):
    user_id = message.from_user.id
    username = message.from_user.username
    first_name = message.from_user.first_name
    last_name = message.from_user.last_name
    
    # Save user to database
    save_user(user_id, username, first_name, last_name)
    update_user_activity(user_id)
    
    # Send log to channel (only for new users)
    if user_id not in logged_users:
        send_user_log(user_id, username, first_name, last_name)
    
    if check_membership(user_id):
        # User is member of all channels
        welcome_text = f"""✨ **Welcome {first_name}!** ✨

🤖 **Welcome to the File Editing Bot!**

📁 **What I can do for you:**
• 📷 Add custom thumbnails to your files
• 📝 Add custom captions to your files  
• ✏️ Rename your files
• 📥 Download customized files

🚀 **How to use:**
1. Send me a `.py` file
2. Customize it using the buttons
3. Download your enhanced file!

💡 **Pro Tip:** You can customize multiple aspects of your file before downloading!

🔧 **Need help?** Use /help command

*Bot by @SudeepHu*"""
        bot.send_message(message.chat.id, welcome_text, parse_mode='Markdown')
        clear_user_session(user_id)  # Clear any previous session
    else:
        # User needs to join channels
        join_text = """📢 **Channel Membership Required** 

To use this amazing bot, you need to join our channels first! 

✨ **Benefits of joining:**
• Get access to this powerful file editor
• Stay updated with latest features
• Join our developer community

👇 **Join both channels below and then click Verify:**"""
        bot.send_message(message.chat.id, join_text, parse_mode='Markdown', reply_markup=create_join_keyboard())

# Verify callback handler
@bot.callback_query_handler(func=lambda call: call.data == "verify")
def verify_callback(call):
    user_id = call.from_user.id
    
    if check_membership(user_id):
        welcome_text = f"""✨ **Welcome {call.from_user.first_name}!** ✨

🤖 **Welcome to the File Editing Bot!**

📁 **Ready to enhance your files?** 
Send me a `.py` file and let's get started!

💫 *Bot by @SudeepHu*"""
        bot.edit_message_text(welcome_text, call.message.chat.id, call.message.message_id, parse_mode='Markdown')
        clear_user_session(user_id)
    else:
        bot.answer_callback_query(call.id, "❌ Please join all channels first! Make sure you've joined both channels.", show_alert=True)

# File handler
@bot.message_handler(content_types=['document'])
def handle_file(message):
    user_id = message.from_user.id
    
    if not check_membership(user_id):
        bot.send_message(message.chat.id, "❌ Please join our channels first to use this bot!", reply_markup=create_join_keyboard())
        return
    
    if not message.document.file_name.endswith('.py'):
        bot.send_message(message.chat.id, "❌ Please send a `.py` file only!", parse_mode='Markdown')
        return
    
    # Clear previous session to avoid mixing old data
    clear_user_session(user_id)
    
    # Download file
    file_info = bot.get_file(message.document.file_id)
    downloaded_file = bot.download_file(file_info.file_path)
    
    # Save to temporary file
    with tempfile.NamedTemporaryFile(delete=False, suffix='.py') as temp_file:
        temp_file.write(downloaded_file)
        temp_path = temp_file.name
    
    # Save fresh session
    save_user_session(user_id, file_path=temp_path, original_name=message.document.file_name)
    
    bot.send_message(message.chat.id, "✅ **File downloaded successfully!** \n\n🎛 **Customization Options:**", 
                    parse_mode='Markdown', reply_markup=create_file_options_keyboard(user_id))

# Thumbnail handler
@bot.callback_query_handler(func=lambda call: call.data == "thumbnail")
def thumbnail_callback(call):
    user_id = call.from_user.id
    session = get_user_session(user_id)
    
    if not session:
        bot.answer_callback_query(call.id, "❌ Please send a file first!", show_alert=True)
        return
    
    bot.edit_message_text("📷 **Send the photo you want to use as thumbnail:**", 
                         call.message.chat.id, call.message.message_id, parse_mode='Markdown')
    
    # Register a temporary message handler for this user
    @bot.message_handler(content_types=['photo'], func=lambda message: message.from_user.id == user_id)
    def handle_thumbnail(message):
        # Download photo
        file_info = bot.get_file(message.photo[-1].file_id)
        downloaded_file = bot.download_file(file_info.file_path)
        
        # Save to temporary file
        with tempfile.NamedTemporaryFile(delete=False, suffix='.jpg') as temp_file:
            temp_file.write(downloaded_file)
            temp_path = temp_file.name
        
        # Update session
        save_user_session(user_id, thumbnail_path=temp_path)
        
        bot.send_message(message.chat.id, "✅ **Thumbnail set successfully!** \n\n🎛 **Choose your next action:**", 
                        parse_mode='Markdown', reply_markup=create_processing_keyboard(user_id))

# Caption callback handler - FIXED: Now properly sets caption text only
@bot.callback_query_handler(func=lambda call: call.data == "caption")
def caption_callback(call):
    user_id = call.from_user.id
    session = get_user_session(user_id)
    
    if not session:
        bot.answer_callback_query(call.id, "❌ Please send a file first!", show_alert=True)
        return
    
    bot.edit_message_text("📝 **Please send the caption text that will appear below your file:**", 
                         call.message.chat.id, call.message.message_id, parse_mode='Markdown')
    
    # Register a temporary message handler for this user
    @bot.message_handler(func=lambda message: message.from_user.id == user_id and not message.text.startswith('/'))
    def handle_caption(message):
        caption_text = message.text
        
        # Update session - ONLY set caption, don't touch file_name
        save_user_session(user_id, caption=caption_text)
        
        bot.send_message(message.chat.id, f"✅ **Caption set successfully!** \n\n📝 **Your caption:** {caption_text}\n\n🎛 **Choose your next action:**", 
                        parse_mode='Markdown', reply_markup=create_processing_keyboard(user_id))

# Rename callback handler - This should change the file name only
@bot.callback_query_handler(func=lambda call: call.data == "rename")
def rename_callback(call):
    user_id = call.from_user.id
    session = get_user_session(user_id)
    
    if not session:
        bot.answer_callback_query(call.id, "❌ Please send a file first!", show_alert=True)
        return
    
    bot.edit_message_text("📝 **What do you want to name the file?** \n\n💡 *Just type the name without .py extension*", 
                         call.message.chat.id, call.message.message_id, parse_mode='Markdown')
    
    # Register a temporary message handler for this user
    @bot.message_handler(func=lambda message: message.from_user.id == user_id and not message.text.startswith('/'))
    def handle_rename(message):
        new_name = message.text.strip()
        if not new_name.endswith('.py'):
            new_name += '.py'
        
        # Update session - ONLY set file_name, don't touch caption
        save_user_session(user_id, file_name=new_name)
        
        bot.send_message(message.chat.id, f"✅ **File renamed to:** `{new_name}` \n\n🎛 **Choose your next action:**", 
                        parse_mode='Markdown', reply_markup=create_processing_keyboard(user_id))

# Download callback handler - FIXED VERSION
@bot.callback_query_handler(func=lambda call: call.data == "download")
def download_callback(call):
    user_id = call.from_user.id
    session = get_user_session(user_id)
    
    if not session or not session.get('file_path'):
        bot.answer_callback_query(call.id, "❌ No file found! Please send a file first.", show_alert=True)
        return
    
    try:
        # Determine file name
        file_name = session.get('file_name') or session.get('original_name') or 'file.py'
        
        # Read the file
        with open(session['file_path'], 'rb') as file:
            file_data = file.read()
        
        # Prepare document data
        document_data = (file_name, file_data)
        
        # Prepare send parameters
        send_params = {
            'chat_id': call.message.chat.id,
            'document': document_data,
        }
        
        # Add caption if exists - THIS IS THE TEXT THAT APPEARS BELOW THE FILE
        if session.get('caption'):
            send_params['caption'] = session.get('caption')
        
        # Add thumbnail if exists
        if session.get('thumbnail_path') and os.path.exists(session['thumbnail_path']):
            with open(session['thumbnail_path'], 'rb') as thumb_file:
                thumb_data = thumb_file.read()
                # Create thumbnail tuple (filename, data)
                send_params['thumb'] = ('thumbnail.jpg', thumb_data)
        
        # Send the file
        bot.send_document(**send_params)
        bot.answer_callback_query(call.id, "✅ File sent successfully with your customizations!")
        
    except Exception as e:
        error_msg = f"❌ Error sending file: {str(e)}"
        print(error_msg)
        bot.answer_callback_query(call.id, error_msg, show_alert=True)

# Help command
@bot.message_handler(commands=['help'])
def help_command(message):
    help_text = """
🤖 **File Editing Bot Help Guide**

🎯 **How to use this bot:**

1. **Start** → Send `/start` and join our channels
2. **Upload** → Send me a `.py` file
3. **Customize** → Use the buttons to:
   - 📷 **Add Thumbnail** - Set a custom image preview
   - 📝 **Add Caption** - Add text that appears below the file when sent
   - ✏️ **Rename** - Change the actual file name
4. **Download** → Get your enhanced file!

🛠 **Available Commands:**
• `/start` - Start the bot
• `/help` - Show this help message  
• `/ping` - Check bot response time

📁 **Supported Files:** Python files (.py) only

💡 **Important Notes:**
• **Caption**: Text that appears below your file when sent
• **Rename**: Changes the actual file name (what the file is called when downloaded)
• **Thumbnail**: Image preview for your file
• Each new file clears previous customizations

🔧 **Need assistance?** Contact @SudeepHu

*Bot crafted with ❤️ by @SudeepHu*
    """
    bot.send_message(message.chat.id, help_text, parse_mode='Markdown')

# Ping command
@bot.message_handler(commands=['ping'])
def ping_command(message):
    start_time = time.time()
    sent_message = bot.send_message(message.chat.id, "🏓 Pong!")
    end_time = time.time()
    
    latency = round((end_time - start_time) * 1000, 2)
    bot.edit_message_text(f"🏓 **Pong!** \n⏱ **Response time:** `{latency}ms` \n\n⚡ *Bot by @SudeepHu*", 
                         message.chat.id, sent_message.message_id, parse_mode='Markdown')

# Admin commands
@bot.message_handler(commands=['stats'])
def stats_command(message):
    if message.from_user.id != ADMIN_ID:
        bot.send_message(message.chat.id, "❌ You are not authorized to use this command.")
        return
    
    total_users = get_total_users()
    today_users = get_today_users()
    
    stats_text = f"""
📊 **Bot Statistics Dashboard**

👥 **Total Users:** `{total_users}`
📈 **Today's New Users:** `{today_users}`
📊 **Active Sessions:** `{len(logged_users)}`
📢 **Log Channel:** [View Logs]({LOG_CHANNEL_LINK})

*Admin: @SudeepHu*
    """
    bot.send_message(message.chat.id, stats_text, parse_mode='Markdown')

@bot.message_handler(commands=['broadcast'])
def broadcast_command(message):
    if message.from_user.id != ADMIN_ID:
        bot.send_message(message.chat.id, "❌ You are not authorized to use this command.")
        return
    
    if message.reply_to_message:
        users = get_all_users()
        success = 0
        failed = 0
        
        progress_msg = bot.send_message(message.chat.id, f"📢 **Starting broadcast to** `{len(users)}` **users...**", parse_mode='Markdown')
        
        for user_id in users:
            try:
                bot.copy_message(user_id, message.chat.id, message.reply_to_message.message_id)
                success += 1
            except:
                failed += 1
        
        bot.edit_message_text(f"✅ **Broadcast Completed!** \n\n✅ **Success:** `{success}` users \n❌ **Failed:** `{failed}` users \n\n*Admin: @SudeepHu*", 
                             message.chat.id, progress_msg.message_id, parse_mode='Markdown')
        
        # Log broadcast in log channel
        log_message = f"""📢 **Admin Broadcast Sent**

👤 **Admin:** {message.from_user.first_name}
🆔 **Admin ID:** `{message.from_user.id}`
👥 **Sent to:** {success} users
❌ **Failed:** {failed} users
📅 **Time:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"""
        bot.send_message(LOG_CHANNEL_ID, log_message, parse_mode='Markdown')
    else:
        bot.send_message(message.chat.id, "❌ **Please reply to a message to broadcast it.** \n\n💡 *Example: Reply to any message with /broadcast*", parse_mode='Markdown')

# Start the bot
if __name__ == "__main__":
    print("🤖 Bot is starting...")
    print(f"📢 Force Join Channels: {[channel['id'] for channel in CHANNELS]}")
    print(f"📝 Log Channel: {LOG_CHANNEL_ID}")
    print(f"👑 Admin: {ADMIN_ID}")
    print("⚡ Bot by @SudeepHu")
    bot.infinity_polling()

from flask import Flask
from threading import Thread


app = Flask('')

@app.route('/')
def home():
    return "Bot is running"

def run_flask():
    app.run(host='0.0.0.0', port=8080)

def keep_alive():
    Thread(target=run_flask).start()
