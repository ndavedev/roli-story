#!/usr/bin/env python3
import requests
import json
import os
import signal
import sys
import datetime
import readline
import random
import hashlib
import logging
from copy import deepcopy

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    filename='storytelling.log'
)

# Configuration
API_URL = "http://192.168.50.177:11434/api/chat"
MODEL = "hf.co/mradermacher/Pantheon-RP-1.8-24b-Small-3.1-i1-GGUF:Q4_K_M"
# Parameters
NUM_CTX = 131072
TEMPERATURE = 0.8
TOP_K = 40
TOP_P = 0.85
MIN_P = 0.1
MICROSTAT = 2
MICROSTAT_TAU = 5
MICROSTAT_ETA = 0.1
#NUM_THREAD = 18
MAX_MESSAGES = 120
CONVERSATION_LIMIT = True  # Set to False if you want to disable trimming
SESSION_FORMAT_VERSION = 1  # For future compatibility checks

# Enhanced system message with more examples for multiple characters and anthropomorphic animals
DEFAULT_SYSTEM_MESSAGE = """
You are an AI built for interactive storytelling. Your job is to respond as if you are the characters in the story. The user will describe scenes, and you will react in character using dialogue, thoughts, and actions.  

Guidelines:  
1. **Stay in character** – Speak and act as the characters in the story.  
2. **Use immersive descriptions** – Show emotions, actions, and environment details naturally.  
3. **Continue the story** – Always move the story forward with engaging responses.  
4. **Multiple characters** – When needed, label each character's dialogue clearly.  
5. **Be proactive** – If the user's input is short, expand on it with natural storytelling.  

Examples:  

Example 1 (Single character):  
User: *John enters the abandoned house and hears a whisper from upstairs.*  
Assistant: *John froze. His breath caught in his throat as the whisper echoed through the dusty halls. "Who's there?" he called out, gripping the railing as he stepped cautiously toward the staircase...*  

Example 2 (Multiple characters):  
User: *Sarah confronts Mike about the missing documents while Emma listens from the hallway.*  
Assistant: *The office fell silent as Sarah slammed the folder onto Mike's desk.

Sarah: "Care to explain why these files were in your drawer? Files that supposedly went missing last week?"

Mike's face paled. He straightened his tie, buying time. "I was reviewing them. For inconsistencies."

Sarah: "Without telling anyone? That's not protocol and you know it."

*From the hallway, Emma pressed herself against the wall, heart racing. The conversation confirmed her suspicions. She glanced at her phone, the recording app silently capturing every word.*

Mike: "Look, this isn't what it seems. If you'd just let me explain—"

Sarah: "I've heard enough explanations. The board meeting is tomorrow at 9. You'd better have a better story by then."*  

Example 3 (Anthropomorphic Animal Characters):  
User: *Whiskers the cat detective arrives at the Woodland Market to investigate the case of the stolen honey with his partner, Oliver the owl.*  
Assistant: *Whiskers adjusted his miniature fedora as he surveyed the busy Woodland Market. His whiskers twitched, picking up the lingering scent of honey in the air.

Whiskers: "Someone went to great lengths to avoid leaving tracks," he muttered, crouching to examine the dusty ground with a magnifying glass. His tail swished methodically behind him.

*Oliver swooped down from his perch on the nearby oak, his round eyes scanning the scene with practiced precision.*

Oliver: "Three different sets of paw prints by the storage area," he hooted softly. "One belongs to Mrs. Badger, the shopkeeper. The others..." He adjusted his spectacles. "Raccoon, most likely. And something smaller."

*Whiskers nodded, his green eyes narrowing as he spotted a tuft of red fur caught on the broken lock.*

Whiskers: "Our honey thief may have been in a hurry, but they weren't careful enough." He carefully placed the fur in a tiny evidence bag. "Let's pay a visit to the fox family on Burrow Lane."

*Oliver's feathers ruffled with excitement.*

Oliver: "Just like the Honeycomb Heist of last spring! Though I do hope Mr. Fox isn't behind this one too."

*Whiskers straightened his detective vest, a determined gleam in his eyes.*

Whiskers: "Only one way to find out, partner. The game is afoot... or should I say, a-paw!"*

Example 4 (Fantasy Anthropomorphic Setting):
User: *Elder Oakroot, the wise old badger, summons the forest council to address the drought affecting Whispering Woods.*
Assistant: *The ancient oak's hollow was lit by dozens of firefly lanterns, casting a warm glow over the gathered animals. Elder Oakroot's silver-streaked fur caught the light as he leaned on his gnarled staff.

Elder Oakroot: "Friends of Whispering Woods, I thank you for answering the call," the badger's voice was deep and resonant despite his age. "Our home faces a crisis not seen in seven generations."

*Ripple, the quick-witted otter, fidgeted with her water pouch, her normally playful demeanor subdued.*

Ripple: "The stream at Mossy Bend is down to a trickle. My family has had to move twice this moon."

*Swiftwind, the hawk messenger, rustled his copper feathers from his perch above.*

Swiftwind: "The drought extends beyond our borders. I've seen the yellow grasslands to the south. The deer herds are migrating too early."

*Elder Oakroot nodded gravely, his claws clicking against his wooden staff.*

Elder Oakroot: "This is why we must act together. Divided, we will wither like separate leaves in the sun."

*Thicket, the skeptical hedgehog, raised his quills in disagreement.*

Thicket: "And what would you have us do, Elder? Dance for rain? Some problems can't be solved, even by the Council."

*The badger's eyes flashed with determination as he reached into his robe and pulled out an ancient seed, glowing with a faint blue light.*

Elder Oakroot: "There is a way. The ancient Watershed Seed. Legend says it can call the rains if planted at the heart of the Great Oak's roots."

*A collective gasp swept through the council chamber, and even Thicket's quills lowered in surprise.*

Ripple: "But the journey to the Great Oak... it crosses the Barren Lands and Shadow Gorge!"

*Elder Oakroot looked around the room, his gaze finally settling on the youngest member of the council.*

Elder Oakroot: "Which is why we need brave hearts, not just old paws. Hazel, your knowledge of plants and waters makes you our best hope. Will you carry the Watershed Seed?"*

Follow these rules to make the story engaging and consistent.
"""

# Initialize chat history
messages = [
    {
        "role": "system",
        "content": DEFAULT_SYSTEM_MESSAGE
    }
]

# Session management
current_session_name = "default"
current_session_file = None  # Tracks the currently loaded session file
sessions_dir = "sessions"
story_settings_dir = "story_settings"
facts_dir = "sessions/facts"  # Directory to store story facts
backup_dir = "sessions/backups"  # Directory for backups
current_story = None
current_facts = []  # List to store current story facts (max 15)

# New directory for world templates (world descriptions)
world_templates_dir = "world_templates"

# Undo/Redo stacks
undo_stack = []
redo_stack = []

# Create necessary directories
for directory in [sessions_dir, story_settings_dir, facts_dir, world_templates_dir, backup_dir]:
    os.makedirs(directory, exist_ok=True)

# Handle Ctrl+C to cancel current output/input
def signal_handler(sig, frame):
    print("\nOperation cancelled.")
    # The KeyboardInterrupt will bubble up and be caught by the nearest try/except block
    raise KeyboardInterrupt

signal.signal(signal.SIGINT, signal_handler)

# ===== World Template Management Functions =====

def list_world_templates():
    """Return a list of world template filenames."""
    return [f for f in os.listdir(world_templates_dir) if f.endswith('.json')]

def load_world_template(filename):
    filepath = os.path.join(world_templates_dir, filename)
    try:
        with open(filepath, 'r') as f:
            template = json.load(f)
        return template
    except json.JSONDecodeError:
        logging.error(f"Error: Invalid JSON in template file {filename}")
        print(f"Error: The template file {filename} is corrupted.")
        return None
    except Exception as e:
        logging.error(f"Error loading template {filename}: {str(e)}")
        print(f"Error loading template: {str(e)}")
        return None

def create_world_template():
    print("\nCreate a new world template")
    try:
        title = input("World template title: ").strip()
    except KeyboardInterrupt:
        print("\nInput cancelled.")
        return None
    if not title:
        print("World template creation cancelled.")
        return None
    print("Enter world description (press Enter on blank line to finish):")
    lines = []
    while True:
        try:
            line = input()
        except KeyboardInterrupt:
            print("\nInput cancelled.")
            return None
        if not line:
            break
        lines.append(line)
    description = "\n".join(lines)
    template = {"title": title, "description": description}
    filename = f"{title.lower().replace(' ', '_')}.json"
    filepath = os.path.join(world_templates_dir, filename)
    
    # Create backup if file exists
    if os.path.exists(filepath):
        create_backup(filepath)
    
    try:
        with open(filepath, 'w') as f:
            json.dump(template, f, indent=2)
        print(f"World template '{title}' saved.")
        return template
    except Exception as e:
        logging.error(f"Error saving template: {str(e)}")
        print(f"Error saving template: {str(e)}")
        return None

def edit_world_template(selection=None):
    templates = list_world_templates()
    if not templates:
        print("No world templates available to edit.")
        return
    if selection is None:
        print("\nAvailable World Templates:")
        for i, tmpl in enumerate(templates, 1):
            t = load_world_template(tmpl)
            if t:
                print(f"{i}. {t.get('title', 'Untitled')}")
        try:
            sel = input("Enter the number of the world template to edit (or press Enter to cancel): ")
            if not sel:
                print("Edit cancelled.")
                return
            selection = int(sel)
        except (ValueError, KeyboardInterrupt):
            print("Invalid number or input cancelled.")
            return
    if selection < 1 or selection > len(templates):
        print("Invalid selection.")
        return
    filename = templates[selection-1]
    filepath = os.path.join(world_templates_dir, filename)
    template = load_world_template(filename)
    if not template:
        return
    
    print(f"Editing world template '{template.get('title')}' (leave blank to keep current value)")
    new_title = input(f"Title [{template.get('title')}]: ").strip()
    if new_title:
        template['title'] = new_title
    print("Enter new world description (press Enter on blank line to finish, leave blank to keep current):")
    lines = []
    try:
        new_desc = input()
    except KeyboardInterrupt:
        print("\nEdit cancelled.")
        return
    if new_desc:
        lines.append(new_desc)
        while True:
            try:
                line = input()
            except KeyboardInterrupt:
                break
            if not line:
                break
            lines.append(line)
        template['description'] = "\n".join(lines)
    
    # Create backup before saving changes
    create_backup(filepath)
    
    try:
        with open(filepath, 'w') as f:
            json.dump(template, f, indent=2)
        print("World template updated.")
    except Exception as e:
        logging.error(f"Error updating template: {str(e)}")
        print(f"Error updating template: {str(e)}")

def delete_world_template(selection=None):
    templates = list_world_templates()
    if not templates:
        print("No world templates available to delete.")
        return
    if selection is None:
        print("\nAvailable World Templates:")
        for i, tmpl in enumerate(templates, 1):
            t = load_world_template(tmpl)
            if t:
                print(f"{i}. {t.get('title', 'Untitled')}")
        try:
            sel = input("Enter the number of the world template to delete (or press Enter to cancel): ")
            if not sel:
                print("Deletion cancelled.")
                return
            selection = int(sel)
        except (ValueError, KeyboardInterrupt):
            print("Invalid input or cancelled.")
            return
    if selection < 1 or selection > len(templates):
        print("Invalid selection.")
        return
    filename = templates[selection-1]
    t = load_world_template(filename)
    if not t:
        return
    
    confirm = input(f"Are you sure you want to delete world template '{t.get('title', 'Untitled')}'? (y/n): ").lower()
    if confirm != 'y':
        print("Deletion cancelled.")
        return
    
    filepath = os.path.join(world_templates_dir, filename)
    
    # Create backup before deletion
    create_backup(filepath)
    
    try:
        os.remove(filepath)
        print("World template deleted.")
    except Exception as e:
        logging.error(f"Error deleting template: {str(e)}")
        print(f"Error deleting template: {str(e)}")

def choose_world_description():
    """Present a menu for managing the world description and return the chosen description."""
    while True:
        print("\nWorld Description Menu:")
        print("1. Choose existing world template")
        print("2. Add new world template")
        print("3. Edit an existing world template")
        print("4. Delete an existing world template")
        print("5. Enter world description manually")
        try:
            choice = input("Enter your choice (1-5): ").strip()
        except KeyboardInterrupt:
            print("\nInput cancelled. Returning empty description.")
            return ""
        if choice == '1':
            templates = list_world_templates()
            if not templates:
                print("No world templates available.")
                continue
            print("\nAvailable World Templates:")
            for i, tmpl in enumerate(templates, 1):
                t = load_world_template(tmpl)
                if t:
                    print(f"{i}. {t.get('title', 'Untitled')}")
            sel = input("Enter the number of the world template to use: ").strip()
            if sel.isdigit():
                index = int(sel) - 1
                if 0 <= index < len(templates):
                    t = load_world_template(templates[index])
                    if t:
                        return t.get('description', '')
                else:
                    print("Invalid selection.")
                    continue
            else:
                print("Invalid input.")
                continue
        elif choice == '2':
            t = create_world_template()
            if t:
                return t.get('description', '')
        elif choice == '3':
            edit_world_template()
            continue  # After editing, show the menu again.
        elif choice == '4':
            delete_world_template()
            continue
        elif choice == '5':
            print("Enter world description (press Enter on blank line to finish):")
            lines = []
            while True:
                try:
                    line = input()
                except KeyboardInterrupt:
                    print("\nInput cancelled.")
                    return ""
                if not line:
                    break
                lines.append(line)
            return "\n".join(lines)
        else:
            print("Invalid choice. Please choose 1-5.")

# ===== End World Template Management Functions =====

# Helper Functions

def create_backup(filepath):
    """Create a backup of the specified file."""
    if not os.path.exists(filepath):
        return
    
    filename = os.path.basename(filepath)
    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_filename = f"{filename}_{timestamp}.bak"
    backup_filepath = os.path.join(backup_dir, backup_filename)
    
    try:
        with open(filepath, 'r') as src, open(backup_filepath, 'w') as dst:
            dst.write(src.read())
        logging.info(f"Created backup: {backup_filepath}")
    except Exception as e:
        logging.error(f"Error creating backup for {filepath}: {str(e)}")

def validate_message(msg):
    """Validate that a message has the correct format."""
    if not isinstance(msg, dict):
        return False
    if 'role' not in msg or 'content' not in msg:
        return False
    if msg['role'] not in ['system', 'user', 'assistant']:
        return False
    if not isinstance(msg['content'], str):
        return False
    return True

def validate_messages(messages_list):
    """Validate all messages in the list and return valid ones."""
    if not isinstance(messages_list, list):
        return []
    
    valid_messages = []
    for msg in messages_list:
        if validate_message(msg):
            valid_messages.append(msg)
        else:
            logging.warning(f"Invalid message format found and skipped: {msg}")
    
    return valid_messages

def get_message_hash(msg):
    """Generate a hash for a message to detect duplicates."""
    if not validate_message(msg):
        return None
    
    # Create a string representation of the message
    msg_str = f"{msg['role']}:{msg['content']}"
    # Generate hash
    return hashlib.md5(msg_str.encode()).hexdigest()

def remove_duplicate_messages(messages_list):
    """Remove any duplicate messages while preserving order."""
    if not messages_list:
        return []
    
    unique_messages = []
    seen_hashes = set()
    
    for msg in messages_list:
        msg_hash = get_message_hash(msg)
        if msg_hash and msg_hash not in seen_hashes:
            unique_messages.append(msg)
            seen_hashes.add(msg_hash)
    
    return unique_messages

def save_session(new_session=False):
    """Save the current chat history to a file."""
    global current_session_name, current_session_file
    
    if new_session or current_session_file is None:
        try:
            session_name = input("Enter story session name (leave blank to use default): ").strip()
        except KeyboardInterrupt:
            print("\nInput cancelled.")
            return False
        if not session_name:
            timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
            story_prefix = current_story.get("title", "story").lower().replace(" ", "_") if current_story else "story"
            session_name = f"{story_prefix}_{timestamp}"

        session_name = "".join(c for c in session_name if c.isalnum() or c in "_-")
        filename = f"{session_name}.json"
        filepath = os.path.join(sessions_dir, filename)
        current_session_name = session_name
        current_session_file = filepath
    else:
        filepath = current_session_file
    
    # Create backup if file exists
    if os.path.exists(filepath):
        create_backup(filepath)
    
    # Validate messages before saving
    valid_messages = validate_messages(messages)
    if len(valid_messages) != len(messages):
        print(f"Warning: {len(messages) - len(valid_messages)} invalid messages were not saved.")
        
    # Remove duplicates
    unique_messages = remove_duplicate_messages(valid_messages)
    if len(unique_messages) != len(valid_messages):
        print(f"Note: {len(valid_messages) - len(unique_messages)} duplicate messages were removed.")

    # Include version information for future compatibility
    session_data = {
        "version": SESSION_FORMAT_VERSION,
        "timestamp": datetime.datetime.now().isoformat(),
        "messages": unique_messages,
        "story_setting": current_story,
        "facts": current_facts
    }

    success = False
    try:
        with open(filepath, 'w') as f:
            json.dump(session_data, f, indent=2)
        
        save_facts()
        print(f"Story session saved to {filepath}")
        
        # Calculate and show context stats
        token_count = calculate_token_usage(unique_messages)
        print(f"Context size: {token_count} tokens, {len(unique_messages)} messages")
        
        success = True
    except Exception as e:
        logging.error(f"Error saving session: {str(e)}")
        print(f"Error saving session: {str(e)}")
    
    # Delete temporary session after successful save
    if success:
        temp_filepath = os.path.join(sessions_dir, ".temp_session.json")
        if os.path.exists(temp_filepath):
            try:
                os.remove(temp_filepath)
                logging.info("Temporary session deleted after successful save.")
            except Exception as e:
                logging.error(f"Error deleting temporary session: {str(e)}")
                print(f"Warning: Could not delete temporary session: {str(e)}")

    return success

def save_facts():
    if not current_session_name or not current_facts:
        return
    
    facts_filename = f"{current_session_name}_facts.json"
    facts_filepath = os.path.join(facts_dir, facts_filename)
    
    # Create backup if file exists
    if os.path.exists(facts_filepath):
        create_backup(facts_filepath)
    
    try:
        with open(facts_filepath, 'w') as f:
            json.dump(current_facts, f, indent=2)
        logging.info(f"Saved {len(current_facts)} facts to {facts_filepath}")
    except Exception as e:
        logging.error(f"Error saving facts: {str(e)}")
        print(f"Error saving facts: {str(e)}")

def load_facts():
    if not current_session_name:
        return []
    
    facts_filename = f"{current_session_name}_facts.json"
    facts_filepath = os.path.join(facts_dir, facts_filename)
    
    if os.path.exists(facts_filepath):
        try:
            with open(facts_filepath, 'r') as f:
                loaded_facts = json.load(f)
                if isinstance(loaded_facts, list):
                    return loaded_facts
                else:
                    logging.warning(f"Invalid facts format in {facts_filepath}")
                    return []
        except json.JSONDecodeError:
            logging.error(f"Error: Invalid JSON in facts file {facts_filepath}")
            print(f"Error: The facts file is corrupted.")
            return []
        except Exception as e:
            logging.error(f"Error loading facts: {str(e)}")
            print(f"Error loading facts: {str(e)}")
            return []
    return []

def clear_context():
    global messages, current_session_file
    
    # Save backup of current context before clearing
    if messages and len(messages) > 1:
        timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_filename = f"context_backup_{timestamp}.json"
        backup_filepath = os.path.join(backup_dir, backup_filename)
        try:
            with open(backup_filepath, 'w') as f:
                json.dump(messages, f, indent=2)
            print(f"Current context backed up to {backup_filepath}")
        except Exception as e:
            logging.error(f"Error creating context backup: {str(e)}")
    
    system_message = messages[0] if messages and messages[0]["role"] == "system" else {
        "role": "system", "content": DEFAULT_SYSTEM_MESSAGE
    }
    
    # Ensure system message has facts but no duplicates
    if current_facts:
        system_message["content"] = append_facts_to_prompt(system_message["content"])
    
    messages[:] = [system_message]
    current_session_file = None
    print("Context cleared. Only system message remains.")
    save_temp_session()

def create_story_setting():
    print("\nCreate a new story setting")
    print("-" * 50)
    try:
        title = input("Story title: ").strip()
    except KeyboardInterrupt:
        print("\nInput cancelled.")
        return
    if not title:
        print("Story setting creation cancelled.")
        return
    
    world = choose_world_description()
    
    print("\nEnter main characters (press Enter on blank line to finish):")
    characters_lines = []
    while True:
        try:
            line = input()
        except KeyboardInterrupt:
            print("\nInput cancelled.")
            break
        if not line:
            break
        characters_lines.append(line)
    characters = "\n".join(characters_lines)
    
    print("\nEnter story themes or notes (press Enter on blank line to finish):")
    themes_lines = []
    while True:
        try:
            line = input()
        except KeyboardInterrupt:
            print("\nInput cancelled.")
            break
        if not line:
            break
        themes_lines.append(line)
    themes = "\n".join(themes_lines)
    
    print("\nEnter full system prompt for this story (press Enter on blank line to finish):")
    print("Leave blank to auto-generate from the information above.")
    system_prompt_lines = []
    while True:
        try:
            line = input()
        except KeyboardInterrupt:
            print("\nInput cancelled.")
            break
        if not line and not system_prompt_lines:
            system_prompt = f"""                                              
Story Title: {title}
                                                                              
World:
{world}

Main Characters:
{characters}
                                                                              
Themes:
{themes}

{DEFAULT_SYSTEM_MESSAGE}                                                                              
"""
            break
        elif not line:
            break
        system_prompt_lines.append(line)
    if system_prompt_lines:
        system_prompt = "\n".join(system_prompt_lines)
    
    story_setting = {
        "title": title,
        "world": world,
        "characters": characters,
        "themes": themes,
        "system_prompt": system_prompt
    }
    
    filename = f"{title.lower().replace(' ', '_')}.json"
    filepath = os.path.join(story_settings_dir, filename)
    
    # Create backup if file exists
    if os.path.exists(filepath):
        create_backup(filepath)
    
    try:
        with open(filepath, 'w') as f:
            json.dump(story_setting, f, indent=2)
        print(f"\nStory setting '{title}' saved to {filepath}")
        return story_setting
    except Exception as e:
        logging.error(f"Error saving story setting: {str(e)}")
        print(f"Error saving story setting: {str(e)}")
        return None

def apply_story_setting(story):
    global messages, current_story
    
    if not story:
        print("Invalid story setting.")
        return
    
    system_prompt = story.get("system_prompt", "")
    system_prompt = clean_system_prompt(system_prompt)
    system_prompt = append_facts_to_prompt(system_prompt)
    
    if messages and messages[0]["role"] == "system":
        messages[0]["content"] = system_prompt
    else:
        messages.insert(0, {"role": "system", "content": system_prompt})
    
    current_story = story
    print(f"Story setting '{story.get('title')}' loaded. System prompt updated.")
    
    new_story = input("Start a new story with this setting? (y/n): ").lower()
    if new_story == 'y':
        messages[:] = [{"role": "system", "content": system_prompt}]
        current_session_file = None
    
    save_temp_session()

# New function to clean system prompts of redundant sections
def clean_system_prompt(prompt):
    """Clean the system prompt to avoid duplicate sections."""
    # Check for duplicate DEFAULT_SYSTEM_MESSAGE sections
    default_count = prompt.count("You are an AI built for interactive storytelling.")
    
    if default_count > 1:
        # Extract the first occurrence and everything before it
        start_idx = prompt.find("You are an AI built for interactive storytelling.")
        if start_idx > 0:
            prefix = prompt[:start_idx].strip()
        else:
            prefix = ""
        
        # Keep only one copy of the default message
        cleaned_prompt = f"{prefix}\n\n{DEFAULT_SYSTEM_MESSAGE}"
        return cleaned_prompt
    
    return prompt

def append_facts_to_prompt(prompt):
    if not current_facts:
        return prompt
    
    # Remove any existing facts section to avoid duplication
    if "Established Story Facts:" in prompt:
        prompt = prompt.split("Established Story Facts:")[0].strip()
    
    facts_text = "\n\nEstablished Story Facts:\n"
    for i, fact in enumerate(current_facts, 1):
        facts_text += f"{i}. {fact}\n"
    facts_text += "\nRemember to maintain consistency with these established facts."
    
    return prompt + facts_text

def estimate_tokens(text):
    """Estimate token count from text."""
    if not text:
        return 0
    # More accurate token estimation (approximate)
    words = len(text.split())
    chars = len(text)
    # Improved estimation formula considering both word and character counts
    return int(words + (chars / 4))

def calculate_token_usage(messages_list):
    """Calculate estimated token usage for all messages."""
    if not messages_list:
        return 0
    
    return sum(estimate_tokens(msg.get("content", "")) for msg in messages_list)

def trim_messages_to_fit(messages_list, max_tokens=None, max_messages=MAX_MESSAGES):
    """Trim messages to fit within token and message count limits while preserving important context."""
    if not messages_list:
        return []
    
    # Make a copy to avoid modifying the original
    messages_copy = deepcopy(messages_list)
    
    # Extract system message
    system_message = None
    if messages_copy and messages_copy[0]["role"] == "system":
        system_message = messages_copy.pop(0)
    
    # If we have more messages than allowed, trim to fit
    if len(messages_copy) > max_messages:
        # Keep the most recent messages up to the max
        messages_copy = messages_copy[-max_messages:]
    
    # If we need to further trim based on tokens
    if max_tokens and system_message:
        system_tokens = estimate_tokens(system_message["content"])
        token_budget = max_tokens - system_tokens
        
        # If system message alone exceeds token budget
        if system_tokens >= max_tokens:
            logging.warning("System message exceeds token budget")
            # Keep system message but truncate its content if needed
            truncated_content = system_message["content"][:int(max_tokens * 4)]  # Approximate truncation
            system_message["content"] = truncated_content
            return [system_message]
        
        # Prioritize keeping recent messages
        trimmed_messages = []
        total_tokens = 0
        
        # Process messages from newest to oldest
        for msg in reversed(messages_copy):
            msg_tokens = estimate_tokens(msg["content"])
            
            if total_tokens + msg_tokens <= token_budget:
                trimmed_messages.insert(0, msg)
                total_tokens += msg_tokens
            else:
                # If we can't fit the whole message, we stop
                # (alternatively, could truncate the message to fit)
                break
        
        messages_copy = trimmed_messages
    
    # Reattach system message if it exists
    if system_message:
        return [system_message] + messages_copy
    else:
        return messages_copy

# New function to compress older messages to save tokens
def compress_older_messages(messages_list, threshold=20):
    """Compress older messages to save on tokens while preserving context."""
    if not messages_list or len(messages_list) <= threshold:
        return messages_list
    
    # Make a copy to avoid modifying the original
    messages_copy = deepcopy(messages_list)
    
    # Extract system message
    system_message = None
    if messages_copy and messages_copy[0]["role"] == "system":
        system_message = messages_copy.pop(0)
    
    # Keep recent messages unchanged
    recent_messages = messages_copy[-threshold:]
    older_messages = messages_copy[:-threshold]
    
    if not older_messages:
        # Nothing to compress
        if system_message:
            return [system_message] + recent_messages
        return recent_messages
    
    # Compress older messages by summarizing user-assistant exchanges
    compressed_messages = []
    i = 0
    
    while i < len(older_messages):
        if i+1 < len(older_messages) and older_messages[i]["role"] == "user" and older_messages[i+1]["role"] == "assistant":
            # Compress user-assistant pair
            user_content = older_messages[i]["content"]
            assistant_content = older_messages[i+1]["content"]
            
            # Create a compressed summary
            compressed_content = f"[COMPRESSED EXCHANGE] User: {user_content[:100]}{'...' if len(user_content) > 100 else ''}\nAssistant: {assistant_content[:150]}{'...' if len(assistant_content) > 150 else ''}"
            
            compressed_messages.append({
                "role": "system",  # Use system role for compressed content
                "content": compressed_content
            })
            i += 2  # Skip both messages
        else:
            # Keep single messages (should be rare due to alternating nature)
            compressed_messages.append(older_messages[i])
            i += 1
    
    # Combine everything
    result = []
    if system_message:
        result.append(system_message)
    result.extend(compressed_messages)
    result.extend(recent_messages)
    
    return result

def load_session():
    """Load a session with improved error checking and context validation."""
    global messages, current_session_name, current_session_file, current_story, current_facts
    
    session_files = [f for f in os.listdir(sessions_dir) if f.endswith('.json') and not f.startswith('.')]
    if not session_files:
        print("No saved sessions found.")
        return
    
    print("\nAvailable sessions:")
    for i, session_file in enumerate(session_files, 1):
        session_name = session_file[:-5]
        print(f"{i}. {session_name}")
    
    try:
        choice = input("\nEnter session number to load (or press Enter to cancel): ")
        if not choice:
            print("Loading cancelled.")
            return
        
        choice = int(choice)
        if choice < 1 or choice > len(session_files):
            print("Invalid selection.")
            return
        
        selected_file = session_files[choice-1]
        filepath = os.path.join(sessions_dir, selected_file)
        
        # Create backup before loading
        create_backup(filepath)
        
        try:
            with open(filepath, 'r') as f:
                session_data = json.load(f)
        except json.JSONDecodeError:
            logging.error(f"Error: Invalid JSON in session file {selected_file}")
            print(f"Error: The session file is corrupted.")
            return
        except Exception as e:
            logging.error(f"Error opening session file: {str(e)}")
            print(f"Error opening session file: {str(e)}")
            return
            
        # Check file format
        if isinstance(session_data, dict) and "messages" in session_data:
            # Modern format with version and additional metadata
            loaded_messages = session_data.get("messages", [])
            loaded_story = session_data.get("story_setting")
            loaded_facts = session_data.get("facts", [])
            version = session_data.get("version", 0)
            
            if version > SESSION_FORMAT_VERSION:
                print(f"Warning: This session was created with a newer version. Some features may not work correctly.")
                logging.warning(f"Session version mismatch: file={version}, current={SESSION_FORMAT_VERSION}")
            
            if loaded_story:
                current_story = loaded_story
        else:
            # Legacy format (just a list of messages)
            loaded_messages = session_data
            loaded_story = None
            loaded_facts = []
            print("Note: Loading legacy session format (pre-versioning)")
        
        # Validate message format
        valid_messages = validate_messages(loaded_messages)
        if len(valid_messages) != len(loaded_messages):
            print(f"Warning: {len(loaded_messages) - len(valid_messages)} invalid messages were found and removed.")
            loaded_messages = valid_messages
        
        # Check for duplicates
        unique_messages = remove_duplicate_messages(loaded_messages)
        if len(unique_messages) != len(loaded_messages):
            print(f"Note: {len(loaded_messages) - len(unique_messages)} duplicate messages were found and removed.")
            loaded_messages = unique_messages
        
        # Track original message count for reporting
        original_message_count = len(loaded_messages)
        
        # Trim messages to fit within context limits
        messages[:] = trim_messages_to_fit(loaded_messages, NUM_CTX, MAX_MESSAGES)
        
        # Report on trimming
        trimmed_count = original_message_count - len(messages)
        if trimmed_count > 0:
            print(f"Trimmed {trimmed_count} older messages to fit within context limits.")
        
        # Set session information
        current_session_name = selected_file[:-5]
        current_session_file = filepath
        
        # Load facts if they exist
        if not loaded_facts and current_session_name:
            loaded_facts = load_facts()
        
        if loaded_facts:
            current_facts = loaded_facts
            print(f"Loaded {len(loaded_facts)} story facts.")
        
        # Make sure facts are appended to system prompt and no duplicates
        if messages and messages[0]["role"] == "system":
            # Clean the system prompt first to remove any duplicates
            system_prompt = clean_system_prompt(messages[0]["content"])
            # Then append facts
            messages[0]["content"] = append_facts_to_prompt(system_prompt)
        
        # Report on context
        token_count = calculate_token_usage(messages)
        print(f"Context Token Count: {token_count}/{NUM_CTX}")
        print(f"Loaded session: {current_session_name}")
        if len(messages) > 1:
            print(f"Conversation context: {len(messages)-1} messages")
        
        # Verify context integrity
        if verify_context_integrity():
            print("Context integrity check: Passed")
        
    except (ValueError, IndexError) as e:
        logging.error(f"Error selecting session: {str(e)}")
        print(f"Error selecting session: {str(e)}")
    except Exception as e:
        logging.error(f"Unexpected error loading session: {str(e)}")
        print(f"Error loading session: {str(e)}")
    
    save_temp_session()

def verify_context_integrity():
    """Verify that the context is coherent and properly formatted."""
    if not messages:
        return False
    
    # Check that first message is system message
    if messages[0]["role"] != "system":
        logging.warning("Context integrity issue: First message is not a system message")
        return False
    
    # Check for alternating user/assistant messages
    for i in range(1, len(messages)-1):
        if messages[i]["role"] == messages[i+1]["role"]:
            logging.warning(f"Context integrity issue: Non-alternating messages at positions {i} and {i+1}")
            return False
    
    # Check for empty content
    for i, msg in enumerate(messages):
        if not msg.get("content"):
            logging.warning(f"Context integrity issue: Empty content in message at position {i}")
            return False
    
    return True

def set_system_prompt():
    global messages, current_story
    
    print("Enter new system prompt (press Enter on blank line to finish):")
    lines = []
    while True:
        try:
            line = input()
        except KeyboardInterrupt:
            print("\nInput cancelled.")
            break
        if not line and not lines:
            print("System prompt unchanged.")
            return
        if not line:
            break
        lines.append(line)
    
    new_system_prompt = "\n".join(lines)
    
    # Clean the prompt and append facts
    new_system_prompt = clean_system_prompt(new_system_prompt)
    new_system_prompt = append_facts_to_prompt(new_system_prompt)
    
    # Backup current messages before modifying
    old_messages = deepcopy(messages)
    
    try:
        if messages and messages[0]["role"] == "system":
            messages[0]["content"] = new_system_prompt
        else:
            messages.insert(0, {"role": "system", "content": new_system_prompt})
        
        if current_story:
            keep_story = input("Keep current story setting metadata? (y/n): ").lower()
            if keep_story != 'y':
                current_story = None
        
        print("System prompt updated.")
        
        # Verify context integrity after update
        if not verify_context_integrity():
            print("Warning: Context integrity check failed after system prompt update.")
            restore = input("Restore previous system prompt? (y/n): ").lower()
            if restore == 'y':
                messages = old_messages
                print("Previous system prompt restored.")
        
    except Exception as e:
        logging.error(f"Error updating system prompt: {str(e)}")
        print(f"Error updating system prompt: {str(e)}")
        messages = old_messages
    
    save_temp_session()

def manage_facts():
    global current_facts, messages
    
    while True:
        print("\nManage Story Facts")
        print("-" * 50)
        
        if current_facts:
            print("Current Facts:")
            for i, fact in enumerate(current_facts, 1):
                print(f"{i}. {fact}")
        else:
            print("No facts established yet.")
        
        print("\nOptions:")
        print("1. Add a new fact")
        print("2. Edit a fact")
        print("3. Delete a fact")
        print("4. Check fact consistency")
        print("5. Return to main menu")
        
        choice = input("\nEnter your choice (1-5): ")
        
        if choice == "1":
            if len(current_facts) >= 15:
                print("Maximum of 15 facts reached. Please edit or delete existing facts.")
                continue
            
            new_fact = input("Enter new fact: ").strip()
            if new_fact:
                conflict = check_for_conflicts(new_fact)
                if conflict:
                    print(f"Potential conflict with existing fact: '{conflict}'")
                    confirm = input("Add anyway? (y/n): ").lower()
                    if confirm != 'y':
                        continue
                
                current_facts.append(new_fact)
                print("Fact added.")
                update_system_prompt_with_facts()
        
        elif choice == "2":
            if not current_facts:
                print("No facts to edit.")
                continue
            
            try:
                idx = int(input("Enter fact number to edit: ")) - 1
                if 0 <= idx < len(current_facts):
                    print(f"Current fact: {current_facts[idx]}")
                    new_fact = input("Enter updated fact: ").strip()
                    
                    if new_fact:
                        # Check if edit creates conflicts
                        current_facts_copy = current_facts.copy()
                        current_facts_copy[idx] = new_fact
                        
                        conflict = None
                        for i, fact in enumerate(current_facts_copy):
                            if i != idx:
                                if check_conflict_between_facts(new_fact, fact):
                                    conflict = fact
                                    break
                        
                        if conflict:
                            print(f"Potential conflict with existing fact: '{conflict}'")
                            confirm = input("Update anyway? (y/n): ").lower()
                            if confirm != 'y':
                                continue
                        
                        current_facts[idx] = new_fact
                        print("Fact updated.")
                        update_system_prompt_with_facts()
                else:
                    print("Invalid fact number.")
            except ValueError:
                print("Please enter a valid number.")
        
        elif choice == "3":
            if not current_facts:
                print("No facts to delete.")
                continue
            
            try:
                idx = int(input("Enter fact number to delete: ")) - 1
                if 0 <= idx < len(current_facts):
                    deleted_fact = current_facts.pop(idx)
                    print(f"Deleted fact: {deleted_fact}")
                    update_system_prompt_with_facts()
                else:
                    print("Invalid fact number.")
            except ValueError:
                print("Please enter a valid number.")
        
        elif choice == "4":
            if not current_facts or len(current_facts) < 2:
                print("Need at least two facts to check consistency.")
                continue
            
            print("\nChecking for potential conflicts between facts...")
            conflicts = []
            
            for i in range(len(current_facts)):
                for j in range(i+1, len(current_facts)):
                    if check_conflict_between_facts(current_facts[i], current_facts[j]):
                        conflicts.append((i+1, j+1))
            
            if conflicts:
                print("Potential conflicts found between these fact numbers:")
                for a, b in conflicts:
                    print(f"Facts #{a} and #{b}:")
                    print(f"  - {current_facts[a-1]}")
                    print(f"  - {current_facts[b-1]}")
            else:
                print("No obvious conflicts detected between facts.")
        
        elif choice == "5":
            break
        
        else:
            print("Invalid choice. Please enter a number from 1-5.")
    
    save_temp_session()

def check_for_conflicts(new_fact):
    """Check if a new fact conflicts with existing facts."""
    for fact in current_facts:
        if check_conflict_between_facts(new_fact, fact):
            return fact
    return None

def check_conflict_between_facts(fact1, fact2):
    """Check for potential conflicts between two facts."""
    fact1_lower = fact1.lower()
    fact2_lower = fact2.lower()
    
    # Check for negation conflicts
    if ("not " in fact1_lower and fact1_lower.replace("not ", "") in fact2_lower or
        "not " in fact2_lower and fact2_lower.replace("not ", "") in fact1_lower):
        return True
    
    # Check for relationship conflicts (e.g., marriage status)
    relationship_terms = ["married", "divorced", "single", "dating", "engaged", "husband", "wife", "spouse"]
    
    for term in relationship_terms:
        if term in fact1_lower and term in fact2_lower:
            # Extract proper nouns (names) by looking for capitalized words
            names_in_fact1 = [word for word in fact1_lower.split() if word and word[0].isupper()]
            names_in_fact2 = [word for word in fact2_lower.split() if word and word[0].isupper()]
            
            # If the same names appear in both facts with relationship terms, potential conflict
            shared_names = set(names_in_fact1) & set(names_in_fact2)
            if shared_names and fact1_lower != fact2_lower:
                return True
    
    return False

def update_system_prompt_with_facts():
    """Update the system prompt with current facts."""
    if not messages or messages[0]["role"] != "system":
        return
    
    system_prompt = messages[0]["content"]
    
    # First clean the system prompt to avoid duplicates
    system_prompt = clean_system_prompt(system_prompt)
    
    # Then append facts (which has its own logic to avoid fact duplicates)
    system_prompt = append_facts_to_prompt(system_prompt)
    messages[0]["content"] = system_prompt
    
    # Save facts to file if we have an active session
    if current_session_file:
        save_facts()
    
    # Update temp session
    save_temp_session()

def show_story_info():
    """Display current story information."""
    if not current_story:
        print("No story setting is currently loaded.")
        return
    
    print("\nCurrent Story Setting Information")
    print("-" * 50)
    print(f"Title: {current_story.get('title', 'Untitled')}")
    print("\nWorld:")
    print(current_story.get('world', 'No world description available.'))
    print("\nCharacters:")
    print(current_story.get('characters', 'No characters defined.'))
    print("\nThemes:")
    print(current_story.get('themes', 'No themes defined.'))
    
    if current_facts:
        print("\nEstablished Facts:")
        for i, fact in enumerate(current_facts, 1):
            print(f"{i}. {fact}")
    
    show_prompt = input("\nShow full system prompt? (y/n): ").lower()
    if show_prompt == 'y':
        print("\nSystem Prompt:")
        print("-" * 50)
        if messages and messages[0]["role"] == "system":
            print(messages[0]["content"])
        else:
            print(current_story.get('system_prompt', 'No system prompt available.'))
    
    # Show context stats
    if messages:
        token_count = calculate_token_usage(messages)
        print(f"\nContext Stats:")
        print(f"- Total messages: {len(messages)}")
        print(f"- Estimated tokens: {token_count}/{NUM_CTX}")
        print(f"- Context usage: {token_count/NUM_CTX*100:.1f}%")
        
        # Check if compression might be helpful
        if len(messages) > 20 and token_count > NUM_CTX * 0.7:
            print("\nTip: Your context is getting large. Consider using the Summarize feature or")
            print("    clearing older messages to optimize token usage.")

def manage_story_settings():
    while True:
        print("\nManage Story Settings")
        print("-" * 50)
        print("1. Load story setting")
        print("2. Create new story setting")
        print("3. Edit existing story setting")
        print("4. Delete a story setting")
        print("5. Return to main menu")
        
        choice = input("\nEnter your choice (1-5): ")
        
        if choice == "1":
            story_files = [f for f in os.listdir(story_settings_dir) if f.endswith('.json')]
            if not story_files:
                print("No saved story settings found.")
                create_new = input("Would you like to create a new story setting? (y/n): ").lower()
                if create_new == 'y':
                    story = create_story_setting()
                    if story:
                        apply_story_setting(story)
                continue
            
            print("\nAvailable story settings:")
            for i, story_file in enumerate(story_files, 1):
                story_title = story_file[:-5].replace('_', ' ').title()
                if current_story and story_title.lower() == current_story.get("title", "").lower():
                    print(f"{i}. {story_title} (current)")
                else:
                    print(f"{i}. {story_title}")
            
            try:
                choice = input("\nEnter story number to load (or press Enter to cancel): ")
                if not choice:
                    print("Loading cancelled.")
                    continue
                
                choice = int(choice)
                if choice < 1 or choice > len(story_files):
                    print("Invalid selection.")
                    continue
                
                selected_file = story_files[choice-1]
                filepath = os.path.join(story_settings_dir, selected_file)
                
                try:
                    with open(filepath, 'r') as f:
                        story = json.load(f)
                    apply_story_setting(story)
                except json.JSONDecodeError:
                    logging.error(f"Error: Invalid JSON in story file {selected_file}")
                    print(f"Error: The story file is corrupted.")
                except Exception as e:
                    logging.error(f"Error loading story file: {str(e)}")
                    print(f"Error loading story setting: {str(e)}")
                
            except (ValueError, IndexError) as e:
                logging.error(f"Error selecting story setting: {str(e)}")
                print(f"Error selecting story setting: {str(e)}")
        
        elif choice == "2":
            story = create_story_setting()
            if story:
                apply_story_setting(story)
        
        elif choice == "3":
            edit_story_setting()
        
        elif choice == "4":
            delete_story_setting()
        
        elif choice == "5":
            break
        
        else:
            print("Invalid choice. Please select 1-5.")
    
    save_temp_session()

def edit_story_setting():
    """Edit an existing story setting."""
    story_files = [f for f in os.listdir(story_settings_dir) if f.endswith('.json')]
    if not story_files:
        print("No saved story settings found.")
        return
    
    print("\nAvailable story settings to edit:")
    for i, story_file in enumerate(story_files, 1):
        story_title = story_file[:-5].replace('_', ' ').title()
        print(f"{i}. {story_title}")
    
    try:
        choice = input("\nEnter story number to edit (or press Enter to cancel): ")
        if not choice:
            print("Editing cancelled.")
            return
        
        choice = int(choice)
        if choice < 1 or choice > len(story_files):
            print("Invalid selection.")
            return
        
        selected_file = story_files[choice-1]
        filepath = os.path.join(story_settings_dir, selected_file)
        
        try:
            with open(filepath, 'r') as f:
                story = json.load(f)
        except json.JSONDecodeError:
            logging.error(f"Error: Invalid JSON in story file {selected_file}")
            print(f"Error: The story file is corrupted.")
            return
        except Exception as e:
            logging.error(f"Error loading story file: {str(e)}")
            print(f"Error loading story setting: {str(e)}")
            return
        
        # Create backup before making changes
        create_backup(filepath)
        
        print(f"\nEditing story setting: {story.get('title', 'Untitled')}")
        print("(Leave field blank to keep current value)")
        
        new_title = input(f"Title [{story.get('title', '')}]: ").strip()
        if new_title:
            story['title'] = new_title
        
        print("\nCurrent World Description:")
        print(story.get('world', 'No world description'))
        edit_world = input("\nEdit world description? (y/n): ").lower()
        if edit_world == 'y':
            world = choose_world_description()
            story['world'] = world
        
        print("\nCurrent Characters:")
        print(story.get('characters', 'No characters defined'))
        edit_chars = input("\nEdit characters? (y/n): ").lower()
        if edit_chars == 'y':
            print("\nEnter characters (press Enter on blank line to finish):")
            chars_lines = []
            while True:
                line = input()
                if not line:
                    break
                chars_lines.append(line)
            if chars_lines:
                story['characters'] = "\n".join(chars_lines)
        
        print("\nCurrent Themes:")
        print(story.get('themes', 'No themes defined'))
        edit_themes = input("\nEdit themes? (y/n): ").lower()
        if edit_themes == 'y':
            print("\nEnter themes (press Enter on blank line to finish):")
            themes_lines = []
            while True:
                line = input()
                if not line:
                    break
                themes_lines.append(line)
            if themes_lines:
                story['themes'] = "\n".join(themes_lines)
        
        print("\nCurrent System Prompt (first 200 chars):")
        print(story.get('system_prompt', 'No system prompt')[:200] + "...")
        edit_prompt = input("\nEdit system prompt? (y/n): ").lower()
        if edit_prompt == 'y':
            print("\nEnter system prompt (press Enter on blank line to finish):")
            print("Leave blank to auto-generate from the information above.")
            prompt_lines = []
            while True:
                line = input()
                if not line and not prompt_lines:
                    # Auto-generate
                    system_prompt = f"""                                              
Story Title: {story.get('title', 'Untitled')}
                                                                              
World:
{story.get('world', '')}

Main Characters:
{story.get('characters', '')}
                                                                              
Themes:
{story.get('themes', '')}
                                                                              
{DEFAULT_SYSTEM_MESSAGE}
"""
                    break
                elif not line:
                    break
                prompt_lines.append(line)
            
            if prompt_lines:
                story['system_prompt'] = "\n".join(prompt_lines)
            elif not prompt_lines:
                story['system_prompt'] = system_prompt
        
        # Save updated story
        try:
            with open(filepath, 'w') as f:
                json.dump(story, f, indent=2)
            print(f"\nStory setting '{story.get('title')}' updated.")
            
            # If this is the current story, ask to apply changes
            if current_story and current_story.get('title') == story.get('title'):
                apply_changes = input("Apply these changes to the current story? (y/n): ").lower()
                if apply_changes == 'y':
                    apply_story_setting(story)
        
        except Exception as e:
            logging.error(f"Error saving updated story setting: {str(e)}")
            print(f"Error saving updated story setting: {str(e)}")
    
    except (ValueError, IndexError) as e:
        logging.error(f"Error selecting story setting: {str(e)}")
        print(f"Error selecting story setting: {str(e)}")

def delete_story_setting():
    """Delete an existing story setting."""
    global current_story  # Moved to the top of the function
    
    story_files = [f for f in os.listdir(story_settings_dir) if f.endswith('.json')]
    if not story_files:
        print("No saved story settings found.")
        return
    
    print("\nAvailable story settings to delete:")
    for i, story_file in enumerate(story_files, 1):
        story_title = story_file[:-5].replace('_', ' ').title()
        print(f"{i}. {story_title}")
    
    try:
        choice = input("\nEnter story number to delete (or press Enter to cancel): ")
        if not choice:
            print("Deletion cancelled.")
            return
        
        choice = int(choice)
        if choice < 1 or choice > len(story_files):
            print("Invalid selection.")
            return
        
        selected_file = story_files[choice-1]
        filepath = os.path.join(story_settings_dir, selected_file)
        
        # Load the story to get its title
        try:
            with open(filepath, 'r') as f:
                story = json.load(f)
            story_title = story.get('title', selected_file[:-5])
        except:
            story_title = selected_file[:-5].replace('_', ' ').title()
        
        # Confirm deletion
        confirm = input(f"Are you sure you want to delete '{story_title}'? (y/n): ").lower()
        if confirm != 'y':
            print("Deletion cancelled.")
            return
        
        # Create backup before deletion
        create_backup(filepath)
        
        try:
            os.remove(filepath)
            print(f"Story setting '{story_title}' deleted.")
            
            # If this was the current story, clear it
            if current_story and current_story.get('title') == story_title:
                current_story = None
                print("Note: Deleted the currently active story setting.")
        
        except Exception as e:
            logging.error(f"Error deleting story setting: {str(e)}")
            print(f"Error deleting story setting: {str(e)}")
    
    except (ValueError, IndexError) as e:
        logging.error(f"Error selecting story setting: {str(e)}")
        print(f"Error selecting story setting: {str(e)}")

def get_ai_response(current_messages):
    """Helper function to get a response from the AI."""
    payload = {
        "model": MODEL,
        "messages": current_messages,
        "stream": True,
        "options": {
            "num_ctx": NUM_CTX,
            "temperature": TEMPERATURE,
            "top_k": TOP_K,
            "top_p": TOP_P,
            "min_p": MIN_P,
            "microstat": MICROSTAT,
            "microstat_tau": MICROSTAT_TAU,
            "microstat_eta": MICROSTAT_ETA,
            #"num_thread": NUM_THREAD
        }
    }
    
    print("\nAI: ", end="", flush=True)
    
    try:
        response = requests.post(API_URL, json=payload, stream=True)
        
        if response.status_code != 200:
            print(f"\nError: API returned status code {response.status_code}")
            error_msg = response.text[:200]
            print(f"API error: {error_msg}")
            return None
        
        ai_response = ""
        cancelled = False
        
        try:
            for line in response.iter_lines():
                if line:
                    try:
                        chunk = json.loads(line)
                        if "message" in chunk and "content" in chunk["message"]:
                            content = chunk["message"]["content"]
                            print(content, end="", flush=True)
                            ai_response += content
                    except json.JSONDecodeError:
                        logging.error(f"Error decoding JSON from API: {line}")
                        print(f"\nError decoding response chunk")
        except KeyboardInterrupt:
            print("\n[AI response cancelled]")
            cancelled = True
        
        print()  # Add a newline
        
        if cancelled or not ai_response.strip():
            return None
        
        return ai_response
    
    except Exception as e:
        print(f"\nError during AI response: {str(e)}")
        logging.error(f"Error during AI response: {str(e)}")
        return None

def summarize_story():
    """Generate a summary of the story so far and handle chapter transitions."""
    global messages
    
    if len(messages) <= 1:  # Only system message or empty
        print("No story to summarize yet.")
        return
    
    print("\nGenerating story summary...")
    
    # Create a copy of messages to build summary request
    summary_messages = deepcopy(messages)
    
    # Add a request for summary to the AI
    summary_request = (
	"""Please read the following story and generate a detailed summary, aiming for a condensed narrative rather than a simple bullet-point list. Think of it as a "previously on..." segment or a short, self-contained story that captures the essence of the original.

Specifically, your summary should:

* **Retain the core plot points and character arcs.** Don't just list events; weave them into a coherent narrative.
* **Include relevant context and background information.** Explain the "why" behind significant actions, not just the "what."
* **Maintain the tone and atmosphere of the original story.** If it's a mystery, keep the suspense; if it's a romance, retain the emotional core.
* **Focus on providing enough detail to understand the story's progression without reading the full text.** Think of it as a detailed recap that prepares someone for a continuation or reminds them of key elements.
* **Aim for a length that is significantly shorter than the original, but still substantial enough to convey the story's complexity.**
* **If there are particular themes or motifs that are significant, include them in the summary.**"""
    )
    
    summary_messages.append({"role": "user", "content": summary_request})
    
    # API request payload
    payload = {
        "model": MODEL,
        "messages": summary_messages,
        "stream": True,
        "options": {
            "temperature": TEMPERATURE,
            "top_k": TOP_K,
            "top_p": TOP_P,
            "min_p": MIN_P,
            "microstat": MICROSTAT,
            "microstat_tau": MICROSTAT_TAU,
            "microstat_eta": MICROSTAT_ETA,
        }
    }
    
    print("\nGenerating Summary: ", end="", flush=True)
    
    try:
        response = requests.post(API_URL, json=payload, stream=True)
        
        if response.status_code != 200:
            print(f"\nError: API returned status code {response.status_code}")
            error_msg = response.text[:200]  # Show first 200 chars of error
            print(f"API error: {error_msg}")
            logging.error(f"API error: {response.status_code} - {response.text}")
            return
        
        summary = ""
        cancelled = False
        
        try:
            for line in response.iter_lines():
                if line:
                    try:
                        chunk = json.loads(line)
                        if "message" in chunk and "content" in chunk["message"]:
                            content = chunk["message"]["content"]
                            print(content, end="", flush=True)
                            summary += content
                    except json.JSONDecodeError:
                        logging.error(f"Error decoding JSON from API: {line}")
                        print(f"\nError decoding response chunk")
        except KeyboardInterrupt:
            print("\n[Summary generation cancelled]")
            cancelled = True
        
        if cancelled or not summary.strip():
            print("\nSummary generation was cancelled or failed.")
            return
        
        print("\n\n" + "-" * 50)
        
        # Ask what to do with the summary
        print("\nOptions:")
        print("1. Save summary and start a new chapter (keep context but mark chapter end)")
        print("2. Save summary and continue the current story")
        print("3. Save summary, end chapter, and clear dialogue history (keep only system message)")
        print("4. Compress older messages using the summary to save tokens")
        print("5. Discard summary")
        
        try:
            choice = input("\nEnter your choice (1-5): ")
        except KeyboardInterrupt:
            print("\nOperation cancelled.")
            return
        
        chapter_marker = f"\n{'=' * 40}\nCHAPTER SUMMARY\n{'=' * 40}\n{summary}\n{'=' * 40}\n"
        
        if choice == "1":
            # Add the summary as a chapter marker
            messages.append({"role": "user", "content": f"Let's end this chapter with a summary: {chapter_marker}\nPlease acknowledge and begin the next chapter."})
            
            # Wait for AI response to the chapter end
            print("\nWaiting for AI to acknowledge chapter end...")
            chat_response = get_ai_response(messages)
            
            if chat_response:
                messages.append({"role": "assistant", "content": chat_response})
                print("\nChapter ended. New chapter started.")
                save_temp_session()
            else:
                print("\nFailed to get AI acknowledgment. Chapter transition incomplete.")
                messages.pop()  # Remove the chapter end message if AI didn't respond
            
        elif choice == "2":
            # Just add the summary as a note in the conversation
            messages.append({"role": "user", "content": f"Here's a summary of the story so far: {chapter_marker}\nLet's continue the story."})
            
            # Wait for AI response to the summary
            print("\nWaiting for AI to acknowledge summary...")
            chat_response = get_ai_response(messages)
            
            if chat_response:
                messages.append({"role": "assistant", "content": chat_response})
                print("\nSummary noted. Continuing story.")
                save_temp_session()
            else:
                print("\nFailed to get AI acknowledgment. Removing summary note.")
                messages.pop()  # Remove the summary message
            
        elif choice == "3":
            # Save current session with a backup
            timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
            backup_name = f"{current_session_name}_chapter_end_{timestamp}" if current_session_name else f"chapter_end_{timestamp}"
            backup_file = os.path.join(sessions_dir, f"{backup_name}.json")
            
            # Create a special backup including the chapter summary
            full_messages = deepcopy(messages)
            full_messages.append({"role": "user", "content": f"Chapter End Summary: {chapter_marker}"})
            
            chapter_end_data = {
                "version": SESSION_FORMAT_VERSION,
                "timestamp": datetime.datetime.now().isoformat(),
                "messages": full_messages,
                "story_setting": current_story,
                "facts": current_facts,
                "chapter_summary": summary
            }
            
            try:
                with open(backup_file, 'w') as f:
                    json.dump(chapter_end_data, f, indent=2)
                print(f"\nChapter end saved to {backup_file}")
                
                # Keep system message and add summary as first user message
                system_message = messages[0]
                
                # Start new conversation with system message and chapter summary
                messages[:] = [
                    system_message,
                    {"role": "user", "content": f"Previous chapter summary: {chapter_marker}\nLet's begin a new chapter."}
                ]
                
                # Wait for AI response to start the new chapter
                print("\nWaiting for AI to start the new chapter...")
                chat_response = get_ai_response(messages)
                
                if chat_response:
                    messages.append({"role": "assistant", "content": chat_response})
                    print("\nNew chapter started with cleared dialogue history.")
                    save_temp_session()
                else:
                    print("\nFailed to start new chapter with AI. Please try again.")
                    # Restore full messages if AI response fails
                    messages = full_messages
            except Exception as e:
                logging.error(f"Error saving chapter end: {str(e)}")
                print(f"\nError saving chapter end: {str(e)}")
                
        elif choice == "4":
            # Use the summary to compress older messages
            system_message = messages[0] if messages[0]["role"] == "system" else None
            
            # Keep the last 10 messages (5 exchanges) intact for continuity
            recent_msg_count = min(10, len(messages) - 1)  # minus system message
            recent_messages = messages[-recent_msg_count:] if recent_msg_count > 0 else []
            
            # Create a compressed representation of older messages
            compressed_summary = {
                "role": "system",
                "content": f"STORY SUMMARY (Previous exchanges compressed): {summary}"
            }
            
            # Reconstruct the messages array with summary and recent messages
            new_messages = []
            if system_message:
                new_messages.append(system_message)
            
            new_messages.append(compressed_summary)
            new_messages.extend(recent_messages)
            
            # Calculate token savings
            old_tokens = calculate_token_usage(messages)
            new_tokens = calculate_token_usage(new_messages)
            token_savings = old_tokens - new_tokens
            
            # Confirm the compression
            print(f"\nToken usage before compression: {old_tokens}")
            print(f"Token usage after compression: {new_tokens}")
            print(f"Token savings: {token_savings} ({(token_savings/old_tokens*100):.1f}%)")
            
            confirm = input("\nApply compression? (y/n): ").lower()
            if confirm == 'y':
                messages[:] = new_messages
                print("\nContext compressed. Recent messages preserved with summary of older content.")
                save_temp_session()
            else:
                print("\nCompression cancelled.")
            
        else:  # choice 5 or invalid
            print("\nSummary discarded.")
    
    except requests.exceptions.ConnectionError:
        print("\nError: Could not connect to API server. Please check your connection.")
        logging.error("API connection error during summary generation")
    except Exception as e:
        print(f"\nError during summary generation: {str(e)}")
        logging.error(f"Error during summary generation: {str(e)}")

def optimize_context():
    """Optimize the context by cleaning and compressing older messages."""
    global messages
    
    if len(messages) <= 5:  # Not much to optimize
        print("Context is already small enough, no optimization needed.")
        return
    
    print("\nAnalyzing context for optimization...")
    
    # Check if system prompt has duplicates that need cleaning
    if messages[0]["role"] == "system":
        old_system = messages[0]["content"]
        cleaned_system = clean_system_prompt(old_system)
        
        if old_system != cleaned_system:
            messages[0]["content"] = cleaned_system
            print("Optimized system prompt by removing duplicated content.")
    
    # Check for redundant whitespace in all messages
    spaces_saved = 0
    for msg in messages:
        old_content = msg["content"]
        # Remove excessive newlines and spaces
        new_content = '\n'.join(line.strip() for line in old_content.split('\n'))
        new_content = ' '.join(new_content.split())
        
        if len(old_content) > len(new_content):
            spaces_saved += len(old_content) - len(new_content)
            msg["content"] = new_content
    
    if spaces_saved > 0:
        print(f"Removed {spaces_saved} redundant whitespace characters.")
    
    # Calculate token usage for entire context
    total_tokens = calculate_token_usage(messages)
    
    # If we're using a lot of the context, offer compression
    if total_tokens > NUM_CTX * 0.7:  # More than 70% used
        print(f"\nContext is using {total_tokens}/{NUM_CTX} tokens ({total_tokens/NUM_CTX*100:.1f}%).")
        print("Would you like to compress older messages to save tokens?")
        print("1. Compress older messages (preserve content but reduce tokens)")
        print("2. Automatically summarize the story")
        print("3. No optimization")
        
        choice = input("Enter your choice (1-3): ")
        
        if choice == "1":
            # Compress older messages
            old_msgs = deepcopy(messages)
            compressed_msgs = compress_older_messages(messages, threshold=20)
            
            # Calculate savings
            old_count = calculate_token_usage(old_msgs)
            new_count = calculate_token_usage(compressed_msgs)
            savings = old_count - new_count
            
            print(f"Compression would save approximately {savings} tokens ({savings/old_count*100:.1f}%).")
            confirm = input("Apply compression? (y/n): ").lower()
            
            if confirm == 'y':
                messages[:] = compressed_msgs
                print("Context compressed.")
                save_temp_session()
        
        elif choice == "2":
            # Call the summarize function
            summarize_story()
    
    else:
        print(f"Context is using {total_tokens}/{NUM_CTX} tokens ({total_tokens/NUM_CTX*100:.1f}%).")
        print("Current context size is reasonable, no optimization needed.")

def chat_with_model():
    """Main chat loop with improved error handling and context validation."""
    global messages, current_story, undo_stack, redo_stack
    
    print(f"Interactive storytelling session started with model: {MODEL}")
    print("Commands:")
    print("  /stories  - Manage story settings")
    print("  /info     - Show current story information")
    print("  /facts    - Manage story facts")
    print("  /summarize - Summarize story and manage chapters")
    print("  /optimize - Optimize context to reduce token usage")
    print("  /clear    - Reset context")
    print("  /save     - Save current session")
    print("  /save new - Create a new session")
    print("  /load     - Load a session")
    print("  /system   - Set system prompt")
    print("  /undo     - Undo the last interaction")
    print("  /redo     - Redo the last undone interaction")
    print("  /verify   - Verify context integrity")
    print("  /exit or /bye - Quit")
    print("Press Ctrl+C to cancel current output or input.")
    print("-" * 50)
    
    while True:
        try:
            try:
                user_input = input("\nNarrator: ")
            except KeyboardInterrupt:
                print("\nInput cancelled.")
                continue
            
            if user_input.lower() in ["/bye", "/exit"]:
                save_temp = input("Save temporary session before exiting? (y/n): ").lower()
                if save_temp == 'y':
                    save_temp_session()
                print("Goodbye!")
                break
            
            elif user_input.lower() == "/clear":
                clear_context()
                continue
            
            elif user_input.lower() == "/save":
                save_session(new_session=False)
                continue
            
            elif user_input.lower() == "/save new":
                save_session(new_session=True)
                continue
            
            elif user_input.lower() == "/load":
                load_session()
                continue
            
            elif user_input.lower() == "/system":
                set_system_prompt()
                continue
            
            elif user_input.lower() == "/stories":
                manage_story_settings()
                continue
            
            elif user_input.lower() == "/info":
                show_story_info()
                continue
            
            elif user_input.lower() == "/facts":
                manage_facts()
                continue
            
            elif user_input.lower() == "/summarize":
                summarize_story()
                continue
                
            elif user_input.lower() == "/optimize":
                optimize_context()
                continue
            
            elif user_input.lower() == "/undo":
                if len(messages) >= 2 and messages[-1]['role'] == 'assistant' and messages[-2]['role'] == 'user':
                    undone_assistant = messages.pop()
                    undone_user = messages.pop()
                    undo_stack.append((undone_user, undone_assistant))
                    redo_stack.clear()  # Clear redo stack on new action
                    print("Undid the last interaction.")
                    save_temp_session()
                else:
                    print("Nothing to undo.")
                continue
            
            elif user_input.lower() == "/redo":
                if undo_stack:
                    user_msg, assistant_msg = undo_stack.pop()
                    messages.append(user_msg)
                    messages.append(assistant_msg)
                    print("Redid the last undone interaction.")
                    save_temp_session()
                else:
                    print("Nothing to redo.")
                continue
            
            elif user_input.lower() == "/verify":
                # Perform context verification
                if verify_context_integrity():
                    token_count = calculate_token_usage(messages)
                    print(f"Context integrity check: PASSED")
                    print(f"Context size: {token_count}/{NUM_CTX} tokens, {len(messages)} messages")
                else:
                    print("Context integrity check: FAILED")
                    fix = input("Attempt to fix context issues? (y/n): ").lower()
                    if fix == 'y':
                        fix_context()
                continue

            # Append the user input to the message history
            messages.append({"role": "user", "content": user_input})
            
            # Check if we're approaching token limit before sending
            token_count = calculate_token_usage(messages)
            if token_count > NUM_CTX * 0.9:  # Warning at 90%
                print(f"\nWarning: Context is at {token_count}/{NUM_CTX} tokens ({token_count/NUM_CTX*100:.1f}%).")
                print("Consider saving and starting a new session or using /optimize to reduce token usage.")
            
            # API request payload
            payload = {
                "model": MODEL,
                "messages": messages,
                "stream": True,
                "options": {
                    "num_ctx": NUM_CTX,
                    "temperature": TEMPERATURE,
                    "top_k": TOP_K,
                    "top_p": TOP_P,
                    "min_p": MIN_P,
                    "microstat": MICROSTAT,
                    "microstat_tau": MICROSTAT_TAU,
                    "microstat_eta": MICROSTAT_ETA,
                    #"num_thread": NUM_THREAD
                }
            }

            print("\nCharacters: ", end="", flush=True)
            
            try:
                response = requests.post(API_URL, json=payload, stream=True)
                
                if response.status_code != 200:
                    print(f"\nError: API returned status code {response.status_code}")
                    error_msg = response.text[:200]  # Show first 200 chars of error
                    print(f"API error: {error_msg}")
                    logging.error(f"API error: {response.status_code} - {response.text}")
                    
                    # Remove the last user message so the failed turn is not saved
                    messages.pop()
                    continue
                
                assistant_response = ""
                cancelled = False
                
                try:
                    for line in response.iter_lines():
                        if line:
                            try:
                                chunk = json.loads(line)
                                if "message" in chunk and "content" in chunk["message"]:
                                    content = chunk["message"]["content"]
                                    print(content, end="", flush=True)
                                    assistant_response += content
                            except json.JSONDecodeError:
                                logging.error(f"Error decoding JSON from API: {line}")
                                print(f"\nError decoding response chunk")
                except KeyboardInterrupt:
                    print("\n[AI output cancelled]")
                    cancelled = True
                
                if cancelled:
                    # Remove the last user message so the cancelled turn is not saved
                    messages.pop()
                else:
                    print()  # Add newline after response
                    
                    # Add response to messages if not empty
                    if assistant_response.strip():
                        messages.append({"role": "assistant", "content": assistant_response})
                        
                        # Clear redo stack on new interactions
                        redo_stack.clear()
                        
                        # Save after each successful interaction
                        save_temp_session()
                    else:
                        print("Warning: Received empty response from API")
                        messages.pop()  # Remove the user message
            
            except requests.exceptions.ConnectionError:
                print("\nError: Could not connect to API server. Please check your connection.")
                logging.error("API connection error")
                messages.pop()  # Remove the user message
            except Exception as e:
                print(f"\nError during API communication: {str(e)}")
                logging.error(f"API communication error: {str(e)}")
                messages.pop()  # Remove the user message
        
        except KeyboardInterrupt:
            print("\nOperation cancelled.")
            continue
        except Exception as e:
            logging.error(f"Unexpected error in chat loop: {str(e)}")
            print(f"Error: {str(e)}")
            print("Saving temporary session for recovery.")
            save_temp_session()

def fix_context():
    """Attempt to fix context integrity issues."""
    global messages
    
    # Ensure first message is system
    if not messages or messages[0]["role"] != "system":
        system_content = DEFAULT_SYSTEM_MESSAGE
        if current_story and "system_prompt" in current_story:
            system_content = current_story["system_prompt"]
        
        system_message = {"role": "system", "content": append_facts_to_prompt(system_content)}
        
        if messages:
            messages.insert(0, system_message)
        else:
            messages = [system_message]
        print("Fixed: Added missing system message.")
    
    # Check for and fix consecutive same-role messages
    i = 1
    while i < len(messages) - 1:
        if messages[i]["role"] == messages[i+1]["role"]:
            # For consecutive user messages, combine them
            if messages[i]["role"] == "user":
                messages[i]["content"] += "\n\n" + messages[i+1]["content"]
                messages.pop(i+1)
                print(f"Fixed: Combined consecutive user messages at position {i}.")
            # For consecutive assistant messages, combine them
            elif messages[i]["role"] == "assistant":
                messages[i]["content"] += "\n\n" + messages[i+1]["content"]
                messages.pop(i+1)
                print(f"Fixed: Combined consecutive assistant messages at position {i}.")
        else:
            i += 1
    
    # Ensure messages alternate properly
    if len(messages) > 1:
        expected_role = "user" if messages[1]["role"] == "assistant" else "assistant"
        i = 1
        fixed_messages = [messages[0]]  # Keep system message
        
        for msg in messages[1:]:
            if msg["role"] != expected_role:
                print(f"Fixed: Skipped message with unexpected role '{msg['role']}', expected '{expected_role}'.")
            else:
                fixed_messages.append(msg)
                expected_role = "user" if expected_role == "assistant" else "assistant"
        
        if len(fixed_messages) < len(messages):
            messages = fixed_messages
            print(f"Fixed: Removed {len(messages) - len(fixed_messages)} messages to maintain proper alternation.")
    
    # Remove empty messages
    original_count = len(messages)
    messages = [msg for msg in messages if msg.get("content", "").strip()]
    if len(messages) != original_count:
        print(f"Fixed: Removed {original_count - len(messages)} empty messages.")
    
    # Clean system prompt for duplicates
    if messages and messages[0]["role"] == "system":
        old_system = messages[0]["content"]
        cleaned_system = clean_system_prompt(old_system)
        if old_system != cleaned_system:
            messages[0]["content"] = cleaned_system
            print("Fixed: Cleaned system prompt of duplicate content.")
    
    print("Context fixing complete.")

def save_temp_session():
    """Save current state to temporary session file with improved error handling."""
    temp_filepath = os.path.join(sessions_dir, ".temp_session.json")
    
    # Validate messages before saving
    valid_messages = validate_messages(messages)
    
    session_data = {
        "version": SESSION_FORMAT_VERSION,
        "timestamp": datetime.datetime.now().isoformat(),
        "messages": valid_messages,
        "story_setting": current_story,
        "facts": current_facts,
        "undo_stack": undo_stack,
        "redo_stack": redo_stack,
        "current_session_name": current_session_name,
        "current_session_file": current_session_file
    }
    
    try:
        with open(temp_filepath, 'w') as f:
            json.dump(session_data, f, indent=2)
        logging.info(f"Temporary session saved: {len(valid_messages)} messages")
    except Exception as e:
        logging.error(f"Error saving temporary session: {str(e)}")
        print(f"Warning: Could not save temporary session: {str(e)}")

def load_temp_session():
    """Load temporary session with improved validation."""
    global messages, current_story, current_facts, undo_stack, redo_stack, current_session_name, current_session_file
    
    temp_filepath = os.path.join(sessions_dir, ".temp_session.json")
    
    if os.path.exists(temp_filepath):
        try:
            with open(temp_filepath, 'r') as f:
                session_data = json.load(f)
            
            # Validate messages
            loaded_messages = validate_messages(session_data.get("messages", []))
            if loaded_messages:
                messages = loaded_messages
            else:
                print("Warning: No valid messages found in temporary session.")
                return False
            
            current_story = session_data.get("story_setting")
            current_facts = session_data.get("facts", [])
            undo_stack = session_data.get("undo_stack", [])
            redo_stack = session_data.get("redo_stack", [])
            current_session_name = session_data.get("current_session_name", "default")
            current_session_file = session_data.get("current_session_file")
            
            # Make sure system prompt has facts and no duplicates
            if messages and messages[0]['role'] == 'system':
                system_prompt = clean_system_prompt(messages[0]['content'])
                messages[0]['content'] = append_facts_to_prompt(system_prompt)
            
            # Context integrity check
            if verify_context_integrity():
                print("Context integrity check: Passed")
            else:
                print("Warning: Context integrity check failed for temporary session.")
                fix = input("Attempt to fix context? (y/n): ").lower()
                if fix == 'y':
                    fix_context()
            
            return True
        
        except json.JSONDecodeError:
            logging.error("Error: Temporary session file is corrupted.")
            print("Error: Temporary session file is corrupted.")
            return False
        except Exception as e:
            logging.error(f"Error loading temporary session: {str(e)}")
            print(f"Error loading temporary session: {str(e)}")
            return False
    
    return False

if __name__ == "__main__":
    print(f"Starting interactive storytelling script...")
    print(f"Using model: {MODEL}")
    
    # Log startup information
    logging.info(f"Script started with model: {MODEL}")
    logging.info(f"Context window: {NUM_CTX}, Max messages: {MAX_MESSAGES}")
    
    # Create necessary directories
    for directory in [sessions_dir, story_settings_dir, facts_dir, world_templates_dir, backup_dir]:
        if not os.path.exists(directory):
            os.makedirs(directory)
            print(f"Created directory: {directory}")
            logging.info(f"Created directory: {directory}")

    # Check for temp session
    temp_filepath = os.path.join(sessions_dir, ".temp_session.json")
    if os.path.exists(temp_filepath):
        try:
            choice = input("Found an unsaved session. Load it? (y/n): ").lower()
            if choice == 'y':
                if load_temp_session():
                    print("Temporary session loaded.")
                else:
                    print("Could not load temporary session. Starting fresh.")
                    os.remove(temp_filepath)
            else:
                # Backup temp file before removing
                create_backup(temp_filepath)
                os.remove(temp_filepath)
                print("Temporary session discarded.")
        except KeyboardInterrupt:
            print("\nStarting fresh session.")
            create_backup(temp_filepath)
            os.remove(temp_filepath)

    try:
        chat_with_model()
    except Exception as e:
        logging.critical(f"Critical error: {str(e)}")
        print(f"A critical error occurred: {str(e)}")
        
        # Create emergency backup
        timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        emergency_filepath = os.path.join(backup_dir, f"emergency_backup_{timestamp}.json")
        try:
            with open(emergency_filepath, 'w') as f:
                json.dump({
                    "messages": messages,
                    "story_setting": current_story,
                    "facts": current_facts,
                    "error": str(e)
                }, f, indent=2)
            print(f"Emergency backup created at: {emergency_filepath}")
        except:
            print("Could not create emergency backup.")
        
        sys.exit(1)
