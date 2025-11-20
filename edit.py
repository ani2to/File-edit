import os
import tempfile
import time
from flask import Flask
from threading import Thread
from datetime import datetime, date
import telebot
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton, ReplyKeyboardRemove
from pymongo import MongoClient

BOT_TOKEN = os.getenv('BOT_TOKEN')
MONGODB_URI = os.getenv('MONGODB_URI')

bot = telebot.TeleBot(BOT_TOKEN)

CHANNELS = [
    {'username': 'SPBotz', 'link': 'https://t.me/SPBotz', 'id': -1002546105906},
    {'username': 'SPBotz2', 'link': 'https://t.me/+hu1MMHYoW09jZjk1', 'id': -1002551633594}
]

LOG_CHANNEL_ID = -1003465081275
ADMIN_ID = 6302016869

logged_users = set()

client = MongoClient(MONGODB_URI)
db = client['file_editor_bot']
users_collection = db['users']
user_sessions_collection = db['user_sessions']

def save_user(user_id, username, first_name, last_name):
    user_data = {
        'user_id': user_id,
        'username': username,
        'first_name': first_name,
        'last_name': last_name,
        'joined_date': datetime.now(),
        'last_active': datetime.now()
    }
    users_collection.update_one(
        {'user_id': user_id},
        {'$set': user_data},
        upsert=True
    )

def update_user_activity(user_id):
    users_collection.update_one(
        {'user_id': user_id},
        {'$set': {'last_active': datetime.now()}}
    )

def get_user_session(user_id):
    session = user_sessions_collection.find_one({'user_id': user_id})
    if session:
        session.pop('_id', None)
        return session
    return None

def save_user_session(user_id, file_path=None, thumbnail_path=None, caption=None, file_name=None, original_name=None):
    session_data = {'user_id': user_id}
    
    if file_path is not None:
        session_data['file_path'] = file_path
    if thumbnail_path is not None:
        session_data['thumbnail_path'] = thumbnail_path
    if caption is not None:
        session_data['caption'] = caption
    if file_name is not None:
        session_data['file_name'] = file_name
    if original_name is not None:
        session_data['original_name'] = original_name
        
    user_sessions_collection.update_one(
        {'user_id': user_id},
        {'$set': session_data},
        upsert=True
    )

def clear_user_session(user_id):
    session = get_user_session(user_id)
    if session:
        try:
            if session.get('file_path') and os.path.exists(session['file_path']):
                os.remove(session['file_path'])
            if session.get('thumbnail_path') and os.path.exists(session['thumbnail_path']):
                os.remove(session['thumbnail_path'])
        except:
            pass
    
    user_sessions_collection.delete_one({'user_id': user_id})

def get_total_users():
    return users_collection.count_documents({})

def get_today_users():
    today = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
    return users_collection.count_documents({'joined_date': {'$gte': today}})

def get_all_users():
    users = users_collection.find({}, {'user_id': 1})
    return [user['user_id'] for user in users]

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
    except:
        pass

def create_join_keyboard():
    keyboard = InlineKeyboardMarkup()
    keyboard.add(InlineKeyboardButton("📢 Join ", url=CHANNELS[0]['link']))
    keyboard.add(InlineKeyboardButton("📢 Join ", url=CHANNELS[1]['link']))
    keyboard.add(InlineKeyboardButton("✅ Verify Membership", callback_data="verify"))
    return keyboard

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
    
    for i in range(0, len(buttons), 2):
        if i + 1 < len(buttons):
            keyboard.add(buttons[i], buttons[i+1])
        else:
            keyboard.add(buttons[i])
    
    return keyboard

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

@bot.message_handler(commands=['start'])
def start_command(message):
    user_id = message.from_user.id
    username = message.from_user.username
    first_name = message.from_user.first_name
    last_name = message.from_user.last_name
    
    save_user(user_id, username, first_name, last_name)
    update_user_activity(user_id)
    
    if user_id not in logged_users:
        send_user_log(user_id, username, first_name, last_name)
    
    if check_membership(user_id):
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
        clear_user_session(user_id)
    else:
        join_text = """📢 **Channel Membership Required** 

To use this amazing bot, you need to join our channels first! 

✨ **Benefits of joining:**
• Get access to this powerful file editor
• Stay updated with latest features
• Join our developer community

👇 **Join both channels below and then click Verify:**"""
        bot.send_message(message.chat.id, join_text, parse_mode='Markdown', reply_markup=create_join_keyboard())

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

@bot.message_handler(content_types=['document'])
def handle_file(message):
    user_id = message.from_user.id
    
    if not check_membership(user_id):
        bot.send_message(message.chat.id, "❌ Please join our channels first to use this bot!", reply_markup=create_join_keyboard())
        return
    
    if not message.document.file_name.endswith('.py'):
        bot.send_message(message.chat.id, "❌ Please send a `.py` file only!", parse_mode='Markdown')
        return
    
    clear_user_session(user_id)
    
    file_info = bot.get_file(message.document.file_id)
    downloaded_file = bot.download_file(file_info.file_path)
    
    with tempfile.NamedTemporaryFile(delete=False, suffix='.py') as temp_file:
        temp_file.write(downloaded_file)
        temp_path = temp_file.name
    
    save_user_session(user_id, file_path=temp_path, original_name=message.document.file_name)
    
    bot.send_message(message.chat.id, "✅ **File downloaded successfully!** \n\n🎛 **Customization Options:**", 
                    parse_mode='Markdown', reply_markup=create_file_options_keyboard(user_id))

@bot.callback_query_handler(func=lambda call: call.data == "thumbnail")
def thumbnail_callback(call):
    user_id = call.from_user.id
    session = get_user_session(user_id)
    
    if not session:
        bot.answer_callback_query(call.id, "❌ Please send a file first!", show_alert=True)
        return
    
    bot.edit_message_text("📷 **Send the photo you want to use as thumbnail:**", 
                         call.message.chat.id, call.message.message_id, parse_mode='Markdown')
    
    @bot.message_handler(content_types=['photo'], func=lambda message: message.from_user.id == user_id)
    def handle_thumbnail(message):
        file_info = bot.get_file(message.photo[-1].file_id)
        downloaded_file = bot.download_file(file_info.file_path)
        
        with tempfile.NamedTemporaryFile(delete=False, suffix='.jpg') as temp_file:
            temp_file.write(downloaded_file)
            temp_path = temp_file.name
        
        save_user_session(user_id, thumbnail_path=temp_path)
        
        bot.send_message(message.chat.id, "✅ **Thumbnail set successfully!** \n\n🎛 **Choose your next action:**", 
                        parse_mode='Markdown', reply_markup=create_processing_keyboard(user_id))

@bot.callback_query_handler(func=lambda call: call.data == "caption")
def caption_callback(call):
    user_id = call.from_user.id
    session = get_user_session(user_id)
    
    if not session:
        bot.answer_callback_query(call.id, "❌ Please send a file first!", show_alert=True)
        return
    
    bot.edit_message_text("📝 **Please send the caption text that will appear below your file:**", 
                         call.message.chat.id, call.message.message_id, parse_mode='Markdown')
    
    @bot.message_handler(func=lambda message: message.from_user.id == user_id and not message.text.startswith('/'))
    def handle_caption(message):
        caption_text = message.text
        
        save_user_session(user_id, caption=caption_text)
        
        bot.send_message(message.chat.id, f"✅ **Caption set successfully!** \n\n📝 **Your caption:** {caption_text}\n\n🎛 **Choose your next action:**", 
                        parse_mode='Markdown', reply_markup=create_processing_keyboard(user_id))

@bot.callback_query_handler(func=lambda call: call.data == "rename")
def rename_callback(call):
    user_id = call.from_user.id
    session = get_user_session(user_id)
    
    if not session:
        bot.answer_callback_query(call.id, "❌ Please send a file first!", show_alert=True)
        return
    
    bot.edit_message_text("📝 **What do you want to name the file?** \n\n💡 *Just type the name without .py extension*", 
                         call.message.chat.id, call.message.message_id, parse_mode='Markdown')
    
    @bot.message_handler(func=lambda message: message.from_user.id == user_id and not message.text.startswith('/'))
    def handle_rename(message):
        new_name = message.text.strip()
        if not new_name.endswith('.py'):
            new_name += '.py'
        
        save_user_session(user_id, file_name=new_name)
        
        bot.send_message(message.chat.id, f"✅ **File renamed to:** `{new_name}` \n\n🎛 **Choose your next action:**", 
                        parse_mode='Markdown', reply_markup=create_processing_keyboard(user_id))

@bot.callback_query_handler(func=lambda call: call.data == "download")
def download_callback(call):
    user_id = call.from_user.id
    session = get_user_session(user_id)
    
    if not session or not session.get('file_path'):
        bot.answer_callback_query(call.id, "❌ No file found! Please send a file first.", show_alert=True)
        return
    
    try:
        file_name = session.get('file_name') or session.get('original_name') or 'file.py'
        
        with open(session['file_path'], 'rb') as file:
            file_data = file.read()

        document_data = (file_name, file_data)
        
        send_params = {
            'chat_id': call.message.chat.id,
            'document': document_data,
        }
        
        if session.get('caption'):
            send_params['caption'] = session.get('caption')
        
        if session.get('thumbnail_path') and os.path.exists(session['thumbnail_path']):
            with open(session['thumbnail_path'], 'rb') as thumb_file:
                thumb_data = thumb_file.read()
                send_params['thumb'] = ('thumbnail.jpg', thumb_data)
        
        bot.send_document(**send_params)
        bot.answer_callback_query(call.id, "✅ File sent successfully with your customizations!")
        
    except Exception as e:
        error_msg = f"❌ Error sending file: {str(e)}"
        print(error_msg)
        bot.answer_callback_query(call.id, error_msg, show_alert=True)

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
• **Rename**: Changes the actual file name
• **Thumbnail**: Image preview for your file
• Each new file clears previous customizations

🔧 **Need assistance?** Contact @SudeepHu

*🤖Bot By @SudeepHu*
    """
    bot.send_message(message.chat.id, help_text, parse_mode='Markdown')

@bot.message_handler(commands=['ping'])
def ping_command(message):
    start_time = time.time()
    sent_message = bot.send_message(message.chat.id, "🏓 Pong!")
    end_time = time.time()
    
    latency = round((end_time - start_time) * 1000, 2)
    bot.edit_message_text(f"🏓 **Pong!** \n⏱ **Response time:** `{latency}ms` \n\n⚡ *Bot by @SudeepHu*", 
                         message.chat.id, sent_message.message_id, parse_mode='Markdown')

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
        
        log_message = f"""📢 **Admin Broadcast Sent**

👤 **Admin:** {message.from_user.first_name}
🆔 **Admin ID:** `{message.from_user.id}`
👥 **Sent to:** {success} users
❌ **Failed:** {failed} users"""
        bot.send_message(LOG_CHANNEL_ID, log_message, parse_mode='Markdown')
    else:
        bot.send_message(message.chat.id, "❌ **Please reply to a message to broadcast it.** \n\n💡 *Example: Reply to any message with /broadcast*", parse_mode='Markdown')

# ===== FLASK KEEP-ALIVE SETUP =====
app = Flask(__name__)

@app.route('/')
def home():
    return "🤖 Bot is running healthy!"

@app.route('/health')
def health():
    return {"status": "healthy", "users_online": len(logged_users), "timestamp": datetime.now().isoformat()}

def run_flask():
    port = int(os.environ.get("PORT", 8080))
    app.run(host='0.0.0.0', port=port, debug=False, use_reloader=False)

def run_bot():
    """Run bot with error handling and auto-restart"""
    while True:
        try:
            print("🤖 Starting Telegram Bot...")
            bot.remove_webhook()
            time.sleep(2)
            bot.infinity_polling(timeout=60, long_polling_timeout=60)
        except Exception as e:
            print(f"Bot crashed: {e}")
            print("🔄 Restarting bot in 10 seconds...")
            time.sleep(10)

if __name__ == "__main__":
    # Start Flask in background thread
    flask_thread = Thread(target=run_flask, daemon=True)
    flask_thread.start()
    
    # Start bot with auto-restart
    print("🚀 Starting Bot...")
    run_bot()
