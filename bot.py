import telebot
import os
import subprocess
import signal
from telebot import types

# --- CONFIGURATION ---
API_TOKEN = os.getenv("BOT_TOKEN")
bot = telebot.TeleBot(API_TOKEN)

# Dictionary to store project info: {chat_id: {project_name: {process: Popen_obj, filename: str}}}
projects = {}
# Dictionary to track user states
user_states = {}

# Folder to save the uploaded scripts
BASE_DIR = "running_projects"
if not os.path.exists(BASE_DIR):
    os.makedirs(BASE_DIR)

# --- KEYBOARDS ---
def main_menu():
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
    markup.add(types.KeyboardButton("🚀 Make a Bot"), types.KeyboardButton("📁 My All Project"))
    return markup

def project_manage_menu(project_name):
    markup = types.InlineKeyboardMarkup()
    markup.add(types.InlineKeyboardButton(f"🗑️ Delete {project_name}", callback_data=f"del_{project_name}"))
    markup.add(types.InlineKeyboardButton(f"🆙 Update File", callback_data=f"upd_{project_name}"))
    return markup

# --- HANDLERS ---

@bot.message_handler(commands=['start'])
def send_welcome(message):
    bot.reply_to(message, "Welcome! I am your Python Bot Host.", reply_markup=main_menu())

@bot.message_handler(func=lambda message: message.text == "🚀 Make a Bot")
def ask_project_name(message):
    chat_id = message.chat.id
    bot.send_message(chat_id, "Please enter a unique name for your Project:")
    user_states[chat_id] = {'action': 'naming'}

@bot.message_handler(func=lambda message: message.text == "📁 My All Project")
def list_projects(message):
    chat_id = message.chat.id
    if chat_id not in projects or not projects[chat_id]:
        bot.send_message(chat_id, "You don't have any running projects.")
        return

    bot.send_message(chat_id, "Select a project to manage:")
    for p_name in projects[chat_id]:
        bot.send_message(chat_id, f"Project: {p_name}", reply_markup=project_manage_menu(p_name))

# Handler for Project Name and File Uploads
@bot.message_handler(content_types=['text', 'document'])
def handle_uploads(message):
    chat_id = message.chat.id
    state = user_states.get(chat_id)

    if not state:
        return

    # User is sending project name
    if state['action'] == 'naming' and message.content_type == 'text':
        project_name = message.text.replace(" ", "_")
        user_states[chat_id] = {'action': 'uploading', 'p_name': project_name}
        bot.send_message(chat_id, f"Project name '{project_name}' saved. Now please send your .py file (Max 50MB):")

    # User is sending the file
    elif (state['action'] == 'uploading' or state['action'] == 'updating') and message.content_type == 'document':
        if not message.document.file_name.endswith('.py'):
            bot.send_message(chat_id, "❌ Error: Only .py files are allowed.")
            return

        if message.document.file_size > 50 * 1024 * 1024:
            bot.send_message(chat_id, "❌ Error: File is too large. Max size is 50MB.")
            return

        p_name = state['p_name']
        
        # Stop existing process if updating
        if chat_id in projects and p_name in projects[chat_id]:
            try:
                os.kill(projects[chat_id][p_name]['process'].pid, signal.SIGTERM)
            except:
                pass

        # Save file
        file_info = bot.get_file(message.document.file_id)
        downloaded_file = bot.download_file(file_info.file_path)
        
        file_path = os.path.join(BASE_DIR, f"{chat_id}_{p_name}.py")
        with open(file_path, 'wb') as new_file:
            new_file.write(downloaded_file)

        # Start the Python process
        process = subprocess.Popen(['python', file_path])
        
        # Store in projects dict
        if chat_id not in projects:
            projects[chat_id] = {}
        
        projects[chat_id][p_name] = {'process': process, 'filename': file_path}
        
        bot.send_message(chat_id, f"✅ Project '{p_name}' is now running!", reply_markup=main_menu())
        user_states[chat_id] = None

# Callback for Inline Buttons (Delete/Update)
@bot.callback_query_handler(func=lambda call: True)
def callback_inline(call):
    chat_id = call.message.chat.id
    data = call.data

    if data.startswith("del_"):
        p_name = data.split("_")[1]
        if chat_id in projects and p_name in projects[chat_id]:
            # Kill process
            try:
                os.kill(projects[chat_id][p_name]['process'].pid, signal.SIGTERM)
            except:
                pass
            # Delete file
            if os.path.exists(projects[chat_id][p_name]['filename']):
                os.remove(projects[chat_id][p_name]['filename'])
            
            del projects[chat_id][p_name]
            bot.answer_callback_query(call.id, "Project Deleted")
            bot.edit_message_text(f"🗑️ Project '{p_name}' has been deleted.", chat_id, call.message.message_id)

    elif data.startswith("upd_"):
        p_name = data.split("_")[1]
        user_states[chat_id] = {'action': 'updating', 'p_name': p_name}
        bot.send_message(chat_id, f"Please send the new .py file for '{p_name}':")
        bot.answer_callback_query(call.id, "Ready for update")

if __name__ == "__main__":
    print("Bot is running...")
    bot.infinity_polling()
