import os
import discord
from discord.ext import commands
import glob
import re
import json
from datetime import datetime
from keep_alive import keep_alive()

# API key management
API_KEYS_FILE = "api_keys.json"
SEARCH_HISTORY_FILE = "search_history.json"

def load_json_file(filename, default=None):
    if os.path.exists(filename):
        with open(filename, 'r') as f:
            return json.load(f)
    return default or {}

def save_json_file(filename, data):
    with open(filename, 'w') as f:
        json.dump(data, f, indent=2)

def get_api_keys():
    return load_json_file(API_KEYS_FILE)

def get_search_history():
    return load_json_file(SEARCH_HISTORY_FILE)

def save_api_keys(api_keys):
    save_json_file(API_KEYS_FILE, api_keys)

def save_search_history(history):
    save_json_file(SEARCH_HISTORY_FILE, history)

def create_api_key(user_id, is_admin=False):
    api_keys = get_api_keys()
    key = f"key_{user_id}_{datetime.now().strftime('%Y%m%d%H%M%S')}"
    api_keys[key] = {
        "user_id": str(user_id),
        "created_at": datetime.now().isoformat(),
        "is_admin": is_admin,
        "active": True
    }
    save_api_keys(api_keys)
    return key

def is_admin(user_id):
    api_keys = get_api_keys()
    for key_data in api_keys.values():
        if key_data["user_id"] == str(user_id) and key_data["active"] and key_data["is_admin"]:
            return True
    return False

def set_admin(user_id):
    return create_api_key(user_id, is_admin=True)

def check_api_key(user_id):
    api_keys = get_api_keys()
    for key, data in api_keys.items():
        if data["user_id"] == str(user_id) and data["active"]:
            return True
    return False

def get_search_count(user_id):
    history = get_search_history()
    return history.get(str(user_id), 0)

def increment_search_count(user_id):
    history = get_search_history()
    user_id = str(user_id)
    history[user_id] = history.get(user_id, 0) + 1
    save_search_history(history)

intents = discord.Intents.default()
intents.message_content = True
intents.guilds = True

client = commands.Bot(command_prefix="$", intents=intents)
permissions = discord.Permissions(
    send_messages=True,
    read_messages=True,
    read_message_history=True
)

@client.event
async def on_guild_join(guild):
    """Send welcome message when bot joins a server"""
    for channel in guild.text_channels:
        if channel.permissions_for(guild.me).send_messages:
            embed = discord.Embed(
                title="🔍 Sigglit CSINT Bot",
                description="Thank you for adding me! I'm a specialized bot designed to search through breach data for sensitive information.",
                color=0x2F3136
            )
            embed.add_field(
                name="Commands",
                value="""
                `/search` - Search through breach data
                `/createkey` - Create an API key (Admin only)
                `/revokekey` - Revoke an API key (Admin only)
                `/makeadmin` - Make a user an admin (Admin only)
                """,
                inline=False
            )
            embed.add_field(
                name="Usage Limits",
                value="Free users get 10 searches. Contact an admin for unlimited access.",
                inline=False
            )
            await channel.send(embed=embed)
            break

@client.tree.command(name="help", description="Learn how to use the bot")
async def help(interaction: discord.Interaction):
    embed = discord.Embed(
        title="🔍 Sigglit CSINT Bot Help",
        description="A specialized bot for searching through breach data and sensitive information.",
        color=0x2F3136
    )

    embed.add_field(
        name="📋 Basic Usage",
        value="• `/search <term>` - Search for specific terms in breach data\n• `/help` - Show this help message",
        inline=False
    )

    embed.add_field(
        name="🎯 Search Examples",
        value="• Emails\n• Usernames\n• Domains\n• Credit card related info\n• Login credentials",
        inline=False
    )

    embed.add_field(
        name="⚖️ Usage Limits",
        value="• Free users: 10 searches\n• API key holders: Unlimited searches\n• Contact Wonpil or Katuru for API key purchase",
        inline=False
    )

    await interaction.response.send_message(embed=embed)

@client.tree.command(name="search", description="Search through breach data")
async def search(interaction: discord.Interaction, term: str):
    await interaction.response.defer()
    update_user_stats(interaction.user.id, "search")

    user_id = interaction.user.id
    has_api_key = check_api_key(user_id)
    search_count = get_search_count(user_id)

    if not has_api_key and search_count >= 10:
        embed = discord.Embed(
            title="❌ Free Search Limit Reached",
            description="You've used all 10 free searches! To continue searching, please contact either **Wonpil** or **Katuru** to purchase an API key for unlimited access.",
            color=0xFF0000
        )

        embed.add_field(
            name="🔍 Available Breach Data",
            value="• Credit Card & SSN Information\n• Login Credentials\n• SpaceHey Account Data\n• And more...",
            inline=False
        )

        embed.add_field(
            name="💡 Benefits of API Key",
            value="• Unlimited searches\n• Full context for each result\n• Access to all breach files\n• Priority support",
            inline=False
        )

        await interaction.followup.send(embed=embed)
        return

    results = search_files(term)
    if results:
        # Create comprehensive results file
        results_file = f"search_results_{term}.txt"
        with open(results_file, 'w', encoding='utf-8') as f:
            f.write(f"Complete search results for '{term}':\n\n")
            for result in results:
                f.write(f"File: {result['file']}\n")
                if result['related_terms']:
                    f.write(f"Related findings: {', '.join(result['related_terms'])}\n")
                for ctx in result['contexts']:
                    f.write(f"Context:\n{ctx['context']}\n\n")
                f.write("-" * 50 + "\n")

        # Create concise Discord message with most relevant results
        embed = discord.Embed(
            title=f"🔍 Search Results: {term}",
            description="Most relevant matches (full results in attached file)",
            color=0x2F3136
        )

        total_contexts = sum(len(result['contexts']) for result in results)

        # Sort results by relevance (number of matches)
        sorted_results = sorted(results, 
            key=lambda x: len([c for c in x['contexts'] if term.lower() in c['context'].lower()]), 
            reverse=True)

        # Take top 3 most relevant results
        preview_results = sorted_results[:3]

        embed.add_field(
            name="📊 Overview",
            value=f"Found {total_contexts} total matches in {len(results)} files",
            inline=False
        )

        for result in preview_results:
            # Get contexts with exact term match first
            relevant_contexts = [ctx for ctx in result['contexts'] 
                               if term.lower() in ctx['context'].lower()][:2]
            contexts_preview = "\n".join(
                ctx['context'][:200] + "..." if len(ctx['context']) > 200 else ctx['context']
                for ctx in relevant_contexts
            )
            embed.add_field(
                name=f"📄 {result['file']}",
                value=f"```{contexts_preview}```",
                inline=False
            )

        await interaction.followup.send(embed=embed, file=discord.File(results_file))

        if not check_api_key(interaction.user.id):
            increment_search_count(interaction.user.id)
            remaining = 10 - get_search_count(interaction.user.id)
            await interaction.followup.send(f"ℹ️ You have {remaining} free searches remaining.")
    else:
        await interaction.followup.send(f"No files containing '{term}' were found.")

@client.tree.command(name="createkey", description="Create an API key for a user")
async def createkey(interaction: discord.Interaction, user: discord.Member):
    if not interaction.user.guild_permissions.administrator:
        await interaction.response.send_message("❌ Only administrators can create API keys!")
        return

    key = create_api_key(user.id)
    await interaction.response.send_message(f"✅ API key created for {user.mention}: ||{key}||")

@client.tree.command(name="makeadmin", description="Make a user an admin")
async def makeadmin(interaction: discord.Interaction, user: discord.Member):
    if not is_admin(interaction.user.id):
        await interaction.response.send_message("❌ Only administrators can promote users to admin!")
        return

    admin_key = set_admin(user.id)
    await interaction.response.send_message(f"✅ {user.mention} has been made an admin with key: ||{admin_key}||")

@client.tree.command(name="revokekey", description="Revoke an API key")
async def revokekey(interaction: discord.Interaction, key: str):
    if not (is_admin(interaction.user.id) or interaction.user.guild_permissions.administrator):
        await interaction.response.send_message("❌ Only administrators can revoke API keys!")
        return

    api_keys = get_api_keys()
    if key in api_keys:
        api_keys[key]["active"] = False
        save_api_keys(api_keys)
        await interaction.response.send_message(f"✅ API key `{key}` has been revoked.")
    else:
        await interaction.response.send_message("❌ Invalid API key!")

# Admin configurations
BANNED_IPS_FILE = "banned_ips.json"
USER_STATS_FILE = "user_stats.json"

def load_banned_ips():
    return load_json_file(BANNED_IPS_FILE, default=[])

def save_banned_ips(banned_ips):
    save_json_file(BANNED_IPS_FILE, banned_ips)

def load_user_stats():
    return load_json_file(USER_STATS_FILE, default={})

def save_user_stats(stats):
    save_json_file(USER_STATS_FILE, stats)

def update_user_stats(user_id, command_used):
    stats = load_user_stats()
    if str(user_id) not in stats:
        stats[str(user_id)] = {"commands": {}, "total_uses": 0, "last_used": ""}

    stats[str(user_id)]["commands"][command_used] = stats[str(user_id)]["commands"].get(command_used, 0) + 1
    stats[str(user_id)]["total_uses"] += 1
    stats[str(user_id)]["last_used"] = datetime.now().isoformat()
    save_user_stats(stats)

@client.tree.command(name="apistats", description="View API key statistics (Admin only)")
async def apistats(interaction: discord.Interaction):
    if not is_admin(interaction.user.id):
        await interaction.response.send_message("❌ This command is only available to administrators!")
        return

    api_keys = get_api_keys()
    active_keys = sum(1 for k in api_keys.values() if k["active"])
    admin_keys = sum(1 for k in api_keys.values() if k["is_admin"] and k["active"])

    embed = discord.Embed(title="🔑 API Key Statistics", color=0x2F3136)
    embed.add_field(name="Total Keys", value=str(len(api_keys)), inline=True)
    embed.add_field(name="Active Keys", value=str(active_keys), inline=True)
    embed.add_field(name="Admin Keys", value=str(admin_keys), inline=True)

    await interaction.response.send_message(embed=embed)

@client.tree.command(name="userstats", description="View bot usage statistics (Admin only)")
async def userstats(interaction: discord.Interaction):
    if not is_admin(interaction.user.id):
        await interaction.response.send_message("❌ This command is only available to administrators!")
        return

    stats = load_user_stats()
    total_users = len(stats)
    total_commands = sum(user["total_uses"] for user in stats.values())

    embed = discord.Embed(title="📊 Bot Usage Statistics", color=0x2F3136)
    embed.add_field(name="Total Users", value=str(total_users), inline=True)
    embed.add_field(name="Total Commands Used", value=str(total_commands), inline=True)

    # Show top 5 users
    sorted_users = sorted(stats.items(), key=lambda x: x[1]["total_uses"], reverse=True)[:5]
    top_users = "\n".join(f"<@{user_id}>: {data['total_uses']} commands" for user_id, data in sorted_users)
    embed.add_field(name="Top Users", value=top_users or "No data", inline=False)

    await interaction.response.send_message(embed=embed)

@client.tree.command(name="banip", description="Ban an IP address (Admin only)")
async def banip(interaction: discord.Interaction, ip: str):
    if not is_admin(interaction.user.id):
        await interaction.response.send_message("❌ This command is only available to administrators!")
        return

    if not re.match(r"^(?:[0-9]{1,3}\.){3}[0-9]{1,3}$", ip):
        await interaction.response.send_message("❌ Invalid IP address format!")
        return

    banned_ips = load_banned_ips()
    if ip not in banned_ips:
        banned_ips.append(ip)
        save_banned_ips(banned_ips)
        await interaction.response.send_message(f"✅ IP address {ip} has been banned.")
    else:
        await interaction.response.send_message("⚠️ This IP is already banned!")

@client.tree.command(name="addfile", description="Add a file to breaches folder (Admin only)")
async def addfile(interaction: discord.Interaction, filename: str, attachment: discord.Attachment):
    if not is_admin(interaction.user.id):
        await interaction.response.send_message("❌ This command is only available to administrators!")
        return
        
    if not filename.endswith('.txt'):
        await interaction.response.send_message("❌ Only .txt files are allowed!")
        return
        
    try:
        file_path = os.path.join(SEARCH_DIRECTORY, filename)
        await attachment.save(file_path)
        await interaction.response.send_message(f"✅ File '{filename}' has been added to the breaches folder.")
    except Exception as e:
        await interaction.response.send_message(f"❌ Error saving file: {str(e)}")

@client.tree.command(name="serverinfo", description="Get information about the server")
async def serverinfo(interaction: discord.Interaction):
    server = interaction.guild
    embed = discord.Embed(title=f"📊 Server Information: {server.name}", color=0x2F3136)
    embed.add_field(name="Members", value=str(server.member_count), inline=True)
    embed.add_field(name="Created At", value=server.created_at.strftime("%Y-%m-%d"), inline=True)
    embed.add_field(name="Owner", value=server.owner.mention, inline=True)
    await interaction.response.send_message(embed=embed)

@client.tree.command(name="userinfo", description="Get information about a user")
async def userinfo(interaction: discord.Interaction, user: discord.Member = None):
    target = user or interaction.user
    embed = discord.Embed(title=f"👤 User Information: {target.name}", color=0x2F3136)
    embed.add_field(name="Joined Server", value=target.joined_at.strftime("%Y-%m-%d"), inline=True)
    embed.add_field(name="Account Created", value=target.created_at.strftime("%Y-%m-%d"), inline=True)
    embed.add_field(name="Roles", value=", ".join([role.name for role in target.roles[1:]]) or "None", inline=False)
    await interaction.response.send_message(embed=embed)

@client.tree.command(name="listbreaches", description="List all breach files (Admin only)")
async def listbreaches(interaction: discord.Interaction):
    if not is_admin(interaction.user.id):
        await interaction.response.send_message("❌ This command is only available to administrators!")
        return
        
    files = glob.glob(f"{SEARCH_DIRECTORY}/**/*.txt", recursive=True)
    if not files:
        await interaction.response.send_message("No breach files found.")
        return
        
    embed = discord.Embed(title="📁 Available Breach Files", color=0x2F3136)
    for file in files:
        size = os.path.getsize(file) / 1024  # Convert to KB
        embed.add_field(name=os.path.basename(file), value=f"Size: {size:.2f} KB", inline=False)
    
    await interaction.response.send_message(embed=embed)

@client.tree.command(name="deletebreach", description="Delete a breach file (Admin only)")
async def deletebreach(interaction: discord.Interaction, filename: str):
    if not is_admin(interaction.user.id):
        await interaction.response.send_message("❌ This command is only available to administrators!")
        return
        
    file_path = os.path.join(SEARCH_DIRECTORY, filename)
    if not os.path.exists(file_path):
        await interaction.response.send_message("❌ File not found!")
        return
        
    try:
        os.remove(file_path)
        await interaction.response.send_message(f"✅ Successfully deleted {filename}")
    except Exception as e:
        await interaction.response.send_message(f"❌ Error deleting file: {str(e)}")

@client.tree.command(name="unbanip", description="Unban an IP address (Admin only)")
async def unbanip(interaction: discord.Interaction, ip: str):
    if not is_admin(interaction.user.id):
        await interaction.response.send_message("❌ This command is only available to administrators!")
        return

    banned_ips = load_banned_ips()
    if ip in banned_ips:
        banned_ips.remove(ip)
        save_banned_ips(banned_ips)
        await interaction.response.send_message(f"✅ IP address {ip} has been unbanned.")
    else:
        await interaction.response.send_message("⚠️ This IP is not banned!")

# Configure search settings
SEARCH_DIRECTORY = "Breaches"  # Directory containing breach data
SEARCH_TERMS = {
    "email": ["@gmail.com", "@hotmail.com", "@yahoo.com"],
    "password": ["Password:", "🔑Password:"],
    "card": ["visa", "mastercard", "american express"]
}
FILE_EXTENSIONS = [".txt"]

def get_context(content, term, window=2):
    lines = content.split('\n')
    contexts = []
    for i, line in enumerate(lines):
        if term.lower() in line.lower():
            start = max(0, i - window)
            end = min(len(lines), i + window + 1)
            context = lines[start:end]
            contexts.append({
                'line': line.strip(),
                'context': '\n'.join(context).strip()
            })
    return contexts

def cleanup_results_files():
    for file in glob.glob("search_results_*.txt"):
        try:
            os.remove(file)
        except:
            pass

def search_files(term):
    cleanup_results_files()
    results = []
    if not os.path.exists(SEARCH_DIRECTORY):
        os.makedirs(SEARCH_DIRECTORY)

    for ext in FILE_EXTENSIONS:
        files = glob.glob(f"{SEARCH_DIRECTORY}/**/*{ext}", recursive=True)
        for file_path in files:
            try:
                with open(file_path, 'r', encoding='utf-8') as file:
                    content = file.read()
                    if term.lower() in content.lower():
                        # Find related terms and contexts
                        related_terms = SEARCH_TERMS.get(term.lower(), [])
                        related_findings = []
                        contexts = get_context(content, term)

                        for related in related_terms:
                            if related.lower() in content.lower():
                                related_findings.append(related)
                                contexts.extend(get_context(content, related))

                        results.append({
                            'file': os.path.basename(file_path),
                            'related_terms': related_findings,
                            'contexts': contexts
                        })
            except Exception as e:
                print(f"Error reading {file_path}: {e}")
    return results

@client.event
async def on_ready():
    await client.tree.sync()

    # Ensure sigglitcsint has admin privileges
    api_keys = get_api_keys()
    sigglitcsint_has_admin = False
    for key_data in api_keys.values():
        if key_data.get("user_id") == "sigglitcsint" and key_data.get("is_admin", False):
            sigglitcsint_has_admin = True
            break

    if not sigglitcsint_has_admin:
        set_admin("sigglitcsint")
        print('Added sigglitcsint as admin')

    print('We have logged in as {0.user}'.format(client))
    print('Invite link: https://discord.com/api/oauth2/authorize?client_id={}&permissions={}&scope=bot%20applications.commands'.format(
        client.user.id, permissions.value
    ))

@client.event
async def on_message(message):
    if message.author == client.user:
        return

    if message.content.startswith('$hello'):
        await message.channel.send('Hello!')

    elif message.content.startswith('$createkey'):
        if not message.author.guild_permissions.administrator:
            await message.channel.send("❌ Only administrators can create API keys!")
            return

        # Extract mentioned user or use message author
        target_user = message.mentions[0] if message.mentions else message.author
        key = create_api_key(target_user.id)
        await message.channel.send(f"✅ API key created for {target_user.mention}: ||{key}||")

    elif message.content.startswith('$makeadmin'):
        if not is_admin(message.author.id) and message.author.name.lower() != "sigglitcsint":
            await message.channel.send("❌ Only administrators can promote users to admin!")
            return

        target_user = message.mentions[0] if message.mentions else None
        if not target_user:
            await message.channel.send("❌ Please mention a user to make admin!")
            return

        admin_key = set_admin(target_user.id)
        await message.channel.send(f"✅ {target_user.mention} has been made an admin with key: ||{admin_key}||")

    elif message.content.startswith('$revokekey'):
        if not (is_admin(message.author.id) or message.author.guild_permissions.administrator):
            await message.channel.send("❌ Only administrators can revoke API keys!")
            return

        key = message.content.split()[-1]
        api_keys = get_api_keys()
        if key in api_keys:
            api_keys[key]["active"] = False
            save_api_keys(api_keys)
            await message.channel.send(f"✅ API key `{key}` has been revoked.")
        else:
            await message.channel.send("❌ Invalid API key!")

    elif message.content.startswith('$search'):
        user_id = message.author.id
        has_api_key = check_api_key(user_id)
        search_count = get_search_count(user_id)

        if not has_api_key and search_count >= 10:
            embed = discord.Embed(
                title="❌ Free Search Limit Reached",
                description="You've used all 10 free searches! To continue searching, please contact either **Wonpil** or **Katuru** to purchase an API key for unlimited access.",
                color=0xFF0000
            )

            embed.add_field(
                name="🔍 Available Breach Data",
                value="• Credit Card & SSN Information\n• Login Credentials\n• SpaceHey Account Data\n• And more...",
                inline=False
            )

            embed.add_field(
                name="💡 Benefits of API Key",
                value="• Unlimited searches\n• Full context for each result\n• Access to all breach files\n• Priority support",
                inline=False
            )

            await message.channel.send(embed=embed)
            return
        term = message.content[8:].strip()
        if not term:
            await message.channel.send('Please provide a search term!')
            return

        results = search_files(term)
        if results:
            # Create results file
            results_file = f"search_results_{term}.txt"
            with open(results_file, 'w', encoding='utf-8') as f:
                f.write(f"Search results for '{term}':\n\n")
                for result in results:
                    f.write(f"File: {result['file']}\n")
                    if result['related_terms']:
                        f.write(f"Related findings: {', '.join(result['related_terms'])}\n")
                    if result['contexts']:
                        f.write("Relevant excerpts:\n")
                        for ctx in result['contexts']:
                            f.write(f"{ctx['context']}\n\n")
                    f.write("-" * 50 + "\n")

            # Show summary in Discord
            chunks = []
            current_chunk = f"🔍 Search results for '{term}':\n"
            total_contexts = sum(len(result['contexts']) for result in results)

            if total_contexts > 10:  # If we have many results
                preview_results = results[:3]  # Show first 3 files
                current_chunk += f"\n📊 Found {total_contexts} matches in {len(results)} files."
                current_chunk += f"\n📎 Full results saved to {results_file}"
                current_chunk += "\n\n📝 Preview of first 3 files:\n"

            for result in (preview_results if total_contexts > 10 else results):
                result_text = f"\n📄 **{result['file']}**"
                if result['related_terms']:
                    result_text += f"\n   🔎 Related findings: {', '.join(result['related_terms'])}"
                if result['contexts']:
                    result_text += "\n   📝 Relevant excerpts:"
                    # Show only first 2 contexts per file if we have many results
                    contexts_to_show = result['contexts'][:2] if total_contexts > 10 else result['contexts']
                    for ctx in contexts_to_show:
                        context_text = f"\n```\n{ctx['context']}\n```"
                        # Check if adding this context would exceed Discord's limit
                        if len(current_chunk + result_text + context_text) > 1900:
                            chunks.append(current_chunk)
                            current_chunk = context_text
                        else:
                            current_chunk += context_text

                if len(current_chunk + result_text) > 1900:
                    chunks.append(current_chunk)
                    current_chunk = result_text
                else:
                    current_chunk += result_text

            if current_chunk:
                chunks.append(current_chunk)

            for chunk in chunks:
                await message.channel.send(chunk)
        else:
            await message.channel.send(f"No files containing '{term}' were found.")

        if not check_api_key(message.author.id):
            increment_search_count(message.author.id)
            remaining = 10 - get_search_count(message.author.id)
            await message.channel.send(f"ℹ️ You have {remaining} free searches remaining.")

try:
    token = os.getenv("TOKEN") or ""
    if token == "":
        raise Exception("Please add your token to the Secrets pane.")
    client.run(token)
except discord.HTTPException as e:
    if e.status == 429:
        print("The Discord servers denied the connection for making too many requests")
        print("Get help from https://stackoverflow.com/questions/66724687/in-discord-py-how-to-solve-the-error-for-toomanyrequests")
    else:
        raise e