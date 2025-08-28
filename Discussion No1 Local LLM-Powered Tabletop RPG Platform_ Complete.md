<img src="https://r2cdn.perplexity.ai/pplx-full-logo-primary-dark%402x.png" style="height:64px;margin-right:32px"/>

# Local LLM-Powered Tabletop RPG Platform: Complete Guide

Based on extensive research, I've found several proven solutions that can help you create a powerful local AI-powered tabletop RPG platform for you and your friends. Here's a comprehensive breakdown of the best options and implementation approaches.

## Top LLM Solutions for Local Tabletop RPGs

### Best Local LLM Models for RPG/Storytelling

**For Your RTX 4080 SUPER (16GB VRAM):**

1. **Llama 3.1 70B** (with proper quantization) - Excellent for complex storytelling and character consistency[^1_1]
2. **MythoMakiseMerged-13B** - Specifically fine-tuned for roleplay with excellent character consistency[^1_1]
3. **Silicon Masha 7B** - Community favorite for immersive character interactions with strong contextual understanding[^1_1]
4. **DreamGen Opus V1** - Outstanding for story writing and narrative generation[^1_2]
5. **Eva Qwen2.5** variants - Fine-tuned for uncensored storytelling and creative roleplaying[^1_3]

**Recommended Setup:**

- Use **LM Studio** for easy model management and local hosting
- Install **Ollama** as your local LLM server
- Models like **Command-R 35B** and **Gemma 2 27B** variants work excellently on your hardware[^1_4][^1_5]


## Complete Platform Solutions

### Option 1: Existing Open-Source Platforms

**GameMaster.AI** [^1_6]

- **Features:** Web-based single/multiplayer TTRPG experience with AI DM and notetaker
- **Tech Stack:** Node.js, Vue.js, MongoDB Atlas, OpenAI API (can be modified for local LLMs)
- **Pros:** Complete solution, user management, character creation
- **Installation:**

```bash
git clone https://github.com/deckofdmthings/GameMasterAI
npm install
npm start
```


**TD-LLM-DND** [^1_7]

- **Features:** Streamlit-based D\&D adventure generator with local Ollama integration
- **Tech Stack:** Python, Streamlit, Ollama API
- **Pros:** Already designed for local LLMs, character generation, turn-based gameplay
- **Installation:**

```bash
git clone https://github.com/tegridydev/dnd-llm-game
pip install -r requirements.txt
streamlit run app.py
```


### Option 2: Custom Development Framework

**Recommended Tech Stack:**

- **Backend:** Python Flask or Node.js with Socket.IO
- **Frontend:** React.js or Vue.js
- **Real-time:** WebSockets for live multiplayer interaction[^1_8][^1_9]
- **LLM Integration:** Ollama API or LM Studio local server
- **Database:** SQLite for character sheets and game state

**Basic Architecture:**

```
┌─────────────────┐    ┌──────────────────┐    ┌─────────────────┐
│   Web Frontend  │◄──►│   Web Server     │◄──►│  Local LLM      │
│   (Players)     │    │  (Game Logic)    │    │  (AI DM/ST)     │
└─────────────────┘    └──────────────────┘    └─────────────────┘
                              │
                              ▼
                       ┌──────────────────┐
                       │   Character DB   │
                       │   Game State     │
                       └──────────────────┘
```


## Implementation Approaches by RPG System

### For D\&D 5e/d20 Systems

- Use **AI Realm** style character generation with race/class combinations[^1_10]
- Implement SRD-based rules and spell databases
- Focus on combat automation and dice rolling integration


### For World of Darkness (d10 System)

- Character creation with clan/covenant selection for Vampire[^1_11]
- Dice pool mechanics (rolling multiple d10s, counting successes)
- Emphasis on narrative and horror themes
- Social interaction mechanics


### For BESM (Big Eyes Small Mouth)

- **Tri-stat system** (Body/Mind/Soul attributes)[^1_12][^1_13]
- Point-buy character creation with attributes and defects
- Anime/manga themed content and mechanics
- Flexible power level scaling


## Step-by-Step Implementation Plan

### Phase 1: Local LLM Setup

1. **Install LM Studio** and download recommended models
2. **Set up Ollama** for API integration
3. **Test model performance** with RPG prompts and character generation

### Phase 2: Basic Web Platform

```python
# Flask example structure
from flask import Flask, render_template, request
from flask_socketio import SocketIO, emit
import requests  # for Ollama API calls

app = Flask(__name__)
socketio = SocketIO(app, cors_allowed_origins="*")

# Character sheet management
@app.route('/character/<int:char_id>')
def character_sheet(char_id):
    # Load character data
    character = load_character(char_id)
    return render_template('character_sheet.html', character=character)

# Real-time game interaction
@socketio.on('player_action')
def handle_player_action(data):
    # Process player input through LLM
    response = query_local_llm(data['action'], data['context'])
    emit('game_update', response, broadcast=True)
```


### Phase 3: Advanced Features

- **Character sheet integration** with automatic calculations
- **Dice rolling system** with cryptographic security
- **Combat management** with initiative tracking
- **Session persistence** and campaign management


## Recommended Development Tools

### Character Sheet Creation

- **Dynamic character sheets** using HTML/CSS/JavaScript[^1_14]
- **Formula-based calculations** for stats and modifiers
- **Rule system templates** for different RPG systems


### Multiplayer Infrastructure

- **WebSocket communication** for real-time updates[^1_15][^1_16]
- **Session management** with user authentication
- **Voice/video integration** (optional, via third-party services)


## Performance Considerations

**Hardware Requirements:**

- Your AMD Ryzen 9 3900X and RTX 4080 SUPER are perfect for this setup
- 64GB RAM allows for running large models (27B-70B parameters)
- Consider running the web server and LLM on the same machine

**Network Setup:**

- **Port forwarding** for external player access
- **Local network hosting** for friends on the same network
- **VPN solutions** for secure remote play


## Quick Start Recommendation

**For immediate implementation:**

1. **Download LM Studio** and install **Llama 3.1 70B** or **MythoMakiseMerged-13B**
2. **Clone TD-LLM-DND** project for a working D\&D foundation
3. **Modify the system** to support World of Darkness and BESM rules
4. **Add multiplayer functionality** using WebSockets

**For custom development:**

1. **Start with Flask/Python** for rapid prototyping
2. **Implement basic character creation** for your preferred system
3. **Add LLM integration** via Ollama API
4. **Scale up** with real-time multiplayer features

This approach gives you complete control over your RPG platform while leveraging the power of local LLMs to create an engaging, private gaming experience for your group.
<span style="display:none">[^1_17][^1_18][^1_19][^1_20][^1_21][^1_22][^1_23][^1_24][^1_25][^1_26][^1_27][^1_28][^1_29][^1_30][^1_31][^1_32][^1_33][^1_34][^1_35][^1_36][^1_37][^1_38][^1_39][^1_40][^1_41][^1_42][^1_43][^1_44][^1_45][^1_46][^1_47][^1_48][^1_49][^1_50][^1_51][^1_52][^1_53][^1_54][^1_55][^1_56][^1_57][^1_58][^1_59][^1_60][^1_61][^1_62][^1_63][^1_64]</span>

<div style="text-align: center">⁂</div>

[^1_1]: https://blog.lmsa.app/the-best-lm-studio-models-for-roleplay-in-2025

[^1_2]: https://www.youtube.com/watch?v=F3cDVQNW-j8

[^1_3]: https://privatellm.app/blog/eva-qwen-uncensored-ai-role-play-iphone-ipad-mac

[^1_4]: https://www.reddit.com/r/ollama/comments/1fcrpyp/what_is_the_best_llm_for_ollama_for/

[^1_5]: https://nutstudio.imyfone.com/llm-tips/best-llm-for-roleplay/

[^1_6]: https://github.com/deckofdmthings/GameMasterAI

[^1_7]: https://github.com/tegridydev/dnd-llm-game

[^1_8]: https://stackoverflow.com/questions/8161053/are-websockets-suitable-for-real-time-multiplayer-games

[^1_9]: https://pusher.com/blog/websockets-realtime-gaming-low-latency/

[^1_10]: https://airealm.com

[^1_11]: https://www.reddit.com/r/singularity/comments/1m0mxm0/ai_dungeon_master/

[^1_12]: https://en.wikipedia.org/wiki/Big_Eyes,_Small_Mouth

[^1_13]: https://www.rpg.net/reviews/archive/9/9457.phtml

[^1_14]: https://www.youtube.com/watch?v=s5b3P8OUtsU

[^1_15]: https://serialized.net/2020/09/multiplayer/

[^1_16]: https://www.youtube.com/watch?v=cXxEiWudIUY

[^1_17]: https://www.reddit.com/r/LocalLLaMA/comments/1ge19ps/llm_model_for_dnd/

[^1_18]: https://foundryvtt.com/article/hosting/

[^1_19]: https://www.reddit.com/r/ollama/comments/1lbgh6x/dungeo_ai_webui_a_local_roleplay_frontend_for/

[^1_20]: https://www.reddit.com/r/rpg/comments/g4du8w/self_hosted_virtual_tabletop/

[^1_21]: https://www.youtube.com/watch?v=SUeIsSML2UY

[^1_22]: https://forge-vtt.com

[^1_23]: https://www.youtube.com/watch?v=0N17isGqSMI

[^1_24]: https://lmstudio.ai

[^1_25]: https://railway.com/deploy/X5tR6G

[^1_26]: https://en.wikipedia.org/wiki/AI_Dungeon

[^1_27]: https://github.com/skyloutyr/VTT

[^1_28]: https://roleplayingtool.com

[^1_29]: https://www.reddit.com/r/ollama/comments/1l9py3c/i_built_a_local_ai_dungeon_master_meet_dungeo_ai/

[^1_30]: https://andrewhead.info/assets/pdf/calypso.pdf

[^1_31]: https://www.reddit.com/r/LocalLLaMA/comments/1l9pwk1/i_built_a_local_ai_dungeon_master_meet_dungeo_ai/

[^1_32]: https://www.tenupsoft.com/blog/open-source-ll-ms-hosting-and-running-tools.html

[^1_33]: https://www.ollama.com/laszlo/bob-silly-dungeon-master/blobs/3936a426722a

[^1_34]: https://news.ycombinator.com/item?id=36388563

[^1_35]: https://www.cognativ.com/blogs/post/best-local-llm-tools-for-efficient-model-deployment/257

[^1_36]: https://expmag.com/2020/03/i-slayed-dragons-with-an-ai-powered-dungeon-master/

[^1_37]: https://www.wayline.io/blog/ai-dungeon-masters-algorithmic-storytelling

[^1_38]: https://www.youtube.com/watch?v=cHCQ_df8KSI

[^1_39]: https://fables.gg

[^1_40]: https://www.geocities.ws/magicpencil7/BESM2e.pdf

[^1_41]: https://character.ai/character/NrHui7r_/vampire-the-masquerade-dungeon-master

[^1_42]: https://roll20.net

[^1_43]: https://play.google.com/store/apps/details?id=com.allconade.ai_dungeon\&hl=en

[^1_44]: https://play.google.com/store/apps/details?id=com.shustoff.charactersheet\&hl=en

[^1_45]: https://www.reddit.com/r/RPGdesign/comments/1fplonb/looking_for_a_character_sheet_platform_for_my/

[^1_46]: https://www.hipstersanddragons.com/best-virtual-tabletops/

[^1_47]: https://stackoverflow.com/questions/66367044/how-do-i-use-flasks-url-for-in-a-template

[^1_48]: https://www.freecodecamp.org/news/build-a-real-time-multiplayer-tic-tac-toe-game-using-websockets-and-microservices/

[^1_49]: https://github.com/vttrpg/vttrpg

[^1_50]: https://github.com/orlyyani/text-rpg

[^1_51]: https://www.youtube.com/watch?v=aA_SdbGD64E

[^1_52]: https://expeditiongame.com/source

[^1_53]: https://github.com/SaberSwordBoy/CharacterGenerator

[^1_54]: https://dev.to/sauravmh/building-a-multiplayer-game-using-websockets-1n63

[^1_55]: https://www.reddit.com/r/rpg/comments/phq5f3/open_source_and_free_digital_tools_for_in_person/

[^1_56]: https://www.reddit.com/r/learnpython/comments/1fuej2h/creating_a_character_sheet_creator_with_python/

[^1_57]: https://github.com/topics/ttrpg

[^1_58]: https://blog.devgenius.io/crafting-retro-text-adventure-games-with-modern-ai-ab0d2fe6e2c6

[^1_59]: https://alphazria.com/blog/best-llm-models-for-uncensored-nsfw-chatbots

[^1_60]: http://www.diva-portal.org/smash/get/diva2:1986281/FULLTEXT01.pdf

[^1_61]: https://kextcache.com/uncensored-ai-models/

[^1_62]: https://www.linkedin.com/posts/phcharriere_create-a-dd-npc-agent-with-ollama-and-nemotron-mini-activity-7246048365430325248-PjFT

[^1_63]: https://nutstudio.imyfone.com/local-llm/what-is-local-llm/

[^1_64]: https://www.reddit.com/r/LocalLLaMA/comments/1lfpqs6/current_best_uncensored_model/


---

# Instead of making a python flask web server, and expose it to the internet it is better to build implementation of a telegram group, and the users that get inside that group will be able to setup their respective character sheets etc. It will have Admin commands for system choosing, story base with a LOT of questions for the setting time period local factions or stuff if we choose white wolf system choose vampire or werewolf or mage or changeling or kindred of the east or wraith etc, if it is d\&d choose classic setting or conquest or darker ravenloft theme etc.

Then have the bot use the llm as a dm/st and guide the players through, how does all that sound?

Building the tabletop RPG platform as a Telegram group bot with LLM-based DM/storyteller is an excellent idea for several reasons:

## Benefits of a Telegram Group Bot RPG Platform

- **Easy Access \& Familiar Interface:** Players already use Telegram; no new apps or websites to learn.
- **Built-in User Management:** Telegram handles logins, identities, and messaging so you avoid complex user auth.
- **Group Dynamics:** Group chat mimics tabletop social interaction naturally.
- **Commands \& Interactivity:** You can build intuitive admin commands for system selection, character creation, and game master controls.
- **Rich Media Support:** Text prompts, inline keyboards, and menus for seamless character sheet management.
- **No Need for Exposed Servers:** Bot communicates securely via Telegram APIs without exposing your PC to internet risks.
- **Scalable:** Easily add more players and admins over time without rearchitecting.


## How It Matches Your Project Goals

- You can implement detailed system setups like White Wolf (Vampire, Werewolf, Mage, etc.) and D\&D variants with thematic campaign choices through guided bot interactions.
- The LLM will serve as the AI DM/Storyteller handled inside the bot backend. It responds to player inputs in the group by referencing character sheets and game states you manage.
- Players create and update character sheets via Telegram text prompts or bot commands, stored in a backend database.
- The bot guides the narrative, runs dice rolls virtually, manages turn orders, and answers questions dynamically with LLM DM logic.
- You avoid a complex web UI but retain rich gameplay mechanics accessible through chat commands and natural language.


## Summary

This Telegram-based platform concept aligns perfectly with AI-driven RPG storytelling and multiplayer interaction needs, leveraging a popular messaging platform for ease of use and secure, private access. It minimizes infrastructure complexity while maximizing engagement and accessibility.

If desired, I can help outline technical architecture and core commands for the Telegram bot and how to integrate LLM APIs locally to realize this vision.

---

# And as extra, figure this if the telegram group is a super group, we can create topics inside that so these can be places the users can visit in game, like have the OC Lobby (out of character lobby) to discourse among users, no bot llm interactions there, the players can enter thru the Character topic to manage new character sheets or new members and Admins can add npc's if needed. All characters members or npc's can add information about merits flaws or even their character background.

Then when you visit topics that have the IC prefix like "IC elisium" their character will be in the elisium, and the will be in character and anything the say there will be as their character talking.

And so much more you can suggest things too, ask me stuff about it. Help me make this happen

The concept of using Telegram supergroup topics as in-game locations and functional areas is excellent for immersive tabletop RPG play. It naturally separates player roles, interactions, and administrative functions with the Telegram UI as the backbone.

Here are some tailored suggestions and clarifying questions to help design and build this platform:

## Additional Features and Suggestions

- **Topic-Specific Bot Behavior:**
    - In *OC (Out of Character)* lobby topic, bot only monitors for admin commands (e.g., system setup), no LLM roleplay.
    - In *Character* topic, bot assists with character creation, editing sheets, listing all PCs and NPCs, and managing merits/flaws/background info.
    - In *IC (In Character)* topics (e.g., "IC Elysium"), the bot interprets player messages as character dialogue, narrates environment or NPC actions, and drives story events using the LLM.
- **Character Identity Management:**
    - Bind Telegram user IDs to character profiles so the bot can reference the correct character in IC topics automatically.
    - Allow players with multiple characters to switch context via simple commands.
- **Game Mechanics Integration:**
    - Dice rolling command that outputs results with detailed explanations, supporting d10, d20, or BESM stats.
    - Initiative tracker shared in an IC topic or ephemeral bot messages.
- **NPC Management:**
    - Admin commands to create/edit NPCs with full stats and narrative details.
    - NPCs may automatically intervene in IC topics as controlled by the LLM.
- **Story and World Building:**
    - Admin-driven setup questionnaire guided by the bot to define setting era, factions, tone, etc.
    - Persistent world state recorded and accessible for players via commands.
- **Moderation and Permissions:**
    - Bot enforces permissions, letting only admins run system setup and NPC commands.
    - Limit character edits to owners or trusted roles.
- **Log and Archive System:**
    - Optional logs of IC topic conversations to backstory files or Markdown exports.
    - Player journals or session summaries created on demand.


## Clarifying Questions to Refine

1. Do all players use one shared Telegram account for gameplay or individual accounts linked to characters?
2. How complex do you want combat and stats automation in Telegram? Simple dice with narrative or fully calculated game rules?
3. Should the bot handle private character info (e.g., secret stats, hidden info) via private chats, or is everything public in groups?
4. Do you want the bot to spawn persistent NPC dialogues or automate side quests dynamically?
5. Is integration with voice or other Telegram features something to consider later?

## Next Step Proposal

- Define core commands and flows for OOC lobby, Character, and IC topics.
- Choose tech stack—Node.js or Python with python-telegram-bot or Telegraf libraries, integrating with your local LLM server (LM Studio/Ollama).
- Start building minimal viable bot with character sheet creation and basic DM interactions.
- Gradually add complexity: system setup wizards, dice rolling, NPCs, multiple IC topics.

This architecture makes the game highly interactive, fully leveraging Telegram capabilities while your LLM powers the story dynamically and privately from your local setup.

Would you like me to help draft the bot command specs or assist with a basic prototype code example?

---

# About npc's the ones the Admin will add in the system are the once with preserverance and need to have distinguished information about them saved, the llm will produce npc's as per need and story progression.

Also the models you mentioned, do they play well with Greek speaking audience or the whole project will work better with English speaking members / players?

For NPCs, the admin-added ones will indeed be the persistent, well-detailed NPCs with fully saved stats and backstories, while the LLM will dynamically create additional NPCs on the fly during story progression as needed. This hybrid approach balances rich consistent worldbuilding with flexible storytelling.

Regarding language support for your LLM-powered RPG platform:

### Greek Language Support Overview

- Most major open-source LLMs are primarily trained on English data and show strongest performance in English. So English players experience richer and more accurate AI interactions.
- However, there is an excellent open-source Greek bilingual LLM called **Meltemi** developed by the Institute for Language and Speech Processing (Athena Research Center).
    - Meltemi is based on Mistral-7B, trained on a large Greek corpus with excellent modern Greek language understanding and generation.
    - It comes in instruction-tuned variants suited for chatbots and conversational AI[^4_1][^4_2][^4_3].
- Another option is **OpenEuroLLM-Greek**, a fine-tuned version of Gemma3 for Greek which Ollama offers with good cultural and linguistic accuracy[^4_4].


### Implications for Your Project

- If you want **full LLM Dungeon Master/Storyteller experience in Greek**, Meltemi or OpenEuroLLM-Greek are the best models to use locally.
- For mixed language groups or use cases where English is dominant, you can use powerful English-centric models like Llama 3.1 or MythomakiseMerged for stronger storytelling and switch to Meltemi-based models for Greek player prompts or NPC dialogue.
- You can build a language preference toggle in the Telegram bot that routes query generation to the appropriate model depending on user or group language setting.

This bilingual setup lets you cater to both Greek-speaking players with near-native language interaction, and English-speaking players with broader narrative capabilities.

If the majority of your players are Greek speakers, leveraging Meltemi or OpenEuroLLM-Greek is recommended for the smoothest, most immersive local RPG experience.

Would you like assistance in setting up Meltemi or OpenEuroLLM-Greek on your LM Studio/Ollama environment?
<span style="display:none">[^4_10][^4_5][^4_6][^4_7][^4_8][^4_9]</span>

<div style="text-align: center">⁂</div>

[^4_1]: https://www.ilsp.gr/en/news/meltemi-en/

[^4_2]: https://www.greeknewsagenda.gr/meltemi-the-first-greek-large-language-model/

[^4_3]: http://ic.cti.gr/en/newsroom/meltemi-2.html

[^4_4]: https://ollama.com/jobautomation/OpenEuroLLM-Greek

[^4_5]: https://www.reddit.com/r/LocalLLaMA/comments/1bo3ops/greek_llms/

[^4_6]: https://huggingface.co/ilsp/Meltemi-7B-v1

[^4_7]: https://www.youtube.com/watch?v=iySKzU_ZD4w

[^4_8]: https://cs-msc.uop.gr/sites/default/files/2025-02/Papachristou Ioannis Automated test generation and grading using local LLMs report final.pdf

[^4_9]: https://www.reddit.com/r/LocalLLaMA/comments/1c2kicj/best_way_to_create_an_rp_world/

[^4_10]: https://ollama.com/jobautomation/OpenEuroLLM-Greek:latest/blobs/e0a42594d802


---

# Can there be a system that takes the Greek text the member / player sends out and properly translates it to English and then feed it to the best llm I'll choose for the game system? My machine can handle more than one model running, no problem there, but is there anything that can do that, take a prompt from the user feed it to the Greek llm to properly translate it with meaning relative to the table top roll playing style and then that to feed it to the game system llm that works for world and scenario building etc?

We still are on the discussion part, when this needs to get running I'll ask you to start suggesting methods and platforms etc. But remember I'm using Linux on my system, nowadays cachyos arch Linux and I do have lm studio (as app image) and ollama natively and both properly installed.

Yes, this is definitely possible and a very smart approach to achieve the best RPG storytelling experience for Greek-speaking players while leveraging stronger English LLMs for world-building and gameplay.

## How a Greek-to-English Translation Bridge System Could Work

1. **User Input in Greek:** Player sends Greek text command or roleplay message in Telegram group/topic.
2. **Greek LLM for Contextual Translation:** Input is first sent to a Greek-specialized LLM (e.g., Meltemi or OpenEuroLLM-Greek) fine-tuned for accurate, context-aware translation of RPG-style text from Greek to English. This step preserves RPG meaning and nuances rather than literal word-for-word translation.
3. **English LLM for Game Logic:** The clean, natural English translation output is then fed to your chosen master LLM (e.g., Llama 3.1, MythomakiseMerged) that handles story progression, system mechanics, NPC generation, and world building.
4. **Response Generation \& Translation Back:** When the LLM generates English responses (DM narration, NPC dialogue, etc.), this can optionally be translated back to Greek through the Greek LLM or a dedicated English-to-Greek translation model before sending it back to players.
5. **Telegram Bot Messaging:** The final text (either English or Greek) is posted back to the Telegram group/topic with appropriate character or narrator context.

## Technical Considerations

- **Model Chaining / Pipeline:** Your backend Telegram bot server or script will orchestrate calls between models sequentially, processing input then output through each LLM as needed.
- **Latency:** Translation step adds some delay, but with your Ryzen 9 3900X and RTX 4080 SUPER running models locally via LM Studio and Ollama, it should be smooth.
- **Fine-tuning:** You might want to fine-tune or prompt-engineer your Greek translation LLM to handle RPG terminology, dice rolls, faction names, character concepts accurately.
- **Open-source Libraries:** Use Python libraries to interact with Telegram Bot API, handle NLP pipelines, and call LM Studio/Ollama APIs for local inference.
- **Language Detection:** Automated detection of whether input is Greek or English to decide whether translation step is needed.


## Summary

A **two-model workflow** with a Greek-craft translation LLM feeding an English gameplay LLM is both feasible and aligns perfectly with your hardware and software environment (Arch Linux, LM Studio/AAppImage, Ollama). This pipeline maximizes player immersion and system power.

When ready, I can help design the architecture, suggest open-source tooling, or example Python integration scripts to launch this multilingual RPG bot system.

Would you like me to suggest specific translation LLMs or libraries for chaining the models, or focus on Telegram bot orchestration?

---

# Don't go to translation and libraries for chaining yet, let's just summarize everything we discussed so far in a way that is humanly understandable and also you can reference to if need be.

Go

Here is a clear and human-friendly summary of the tabletop RPG platform project as we have discussed so far, which can also serve as a reference for future development:

***

# Summary: AI-Powered Telegram-Based Tabletop RPG Platform

## Concept Overview

- Build a **Telegram supergroup-based RPG platform**, where players interact through the Telegram app.
- The Telegram group will be a **supergroup** with multiple **topics** representing distinct in-game locations or functional areas.
- An **AI Dungeon Master (DM) / Storyteller (ST)** role is fulfilled by a **local Large Language Model (LLM)** integrated with the bot backend.
- Players create and manage **character sheets** via bot commands and text prompts.
- The bot guides gameplay, runs narratives, manages dice rolls, NPC interactions, and story progression.


## Telegram Group Topic Structure

- **OC Lobby (Out-of-Character):** Players chat casually; no LLM interaction here.
- **Character Topic:** For managing PC and NPC character sheets, editing merits, flaws, backgrounds, and new character creation.
- **IC (In-Character) Topics:** Each represents an in-game place, e.g., "IC Elysium", where players roleplay "in character". All player messages here are treated as character dialogue and narrated by the LLM.
- Additional topics can be added for more locations or gameplay functions as needed.


## AI LLM and Language Handling

- Use powerful English LLMs like **Llama 3.1**, **MythoMakiseMerged-13B**, or **DreamGen Opus V1** for narrative, world-building, and complex gameplay.
- For Greek-speaking players, integrate Greek-specialized LLMs such as **Meltemi** or **OpenEuroLLM-Greek** locally, ensuring culturally and linguistically accurate interactions.
- Optionally, implement a **translation pipeline** where Greek input is translated to English before processing and English responses translated back to Greek, maximizing model effectiveness for bilingual groups.


## NPC Handling

- Admins add **persistent, detailed NPCs** with stored stats and narratives.
- The LLM dynamically creates temporary NPCs during gameplay to keep the story fresh and reactive.


## Gameplay and Bot Features

- Players create and update character sheets through bot commands.
- Bot manages dice rolls for d10 (Old/New World of Darkness), d20 (D\&D), and BESM systems.
- Turn orders, combat management, and faction tracking managed by the bot.
- Admin commands to set game system style, setting themes (classic D\&D, Ravenloft, World of Darkness clans).
- NPC actions and environmental narration driven by the AI DM.
- Permissions restrict who can add/edit characters and run game setup.


## Technical Implementation Highlights

- The bot backend orchestrates dialogue and game commands, communicating with **local LLM servers** (LM Studio and Ollama on your Linux system).
- Telegram Bot API facilitates group message handling, user command parsing, and real-time multiplayer interaction.
- Character profiles linked to Telegram user IDs for seamless IC messaging.
- Topic-aware bot processing: different logic depending on group topic.
- Optionally log game sessions, create player journals, and export narratives.
- Hardware: Your Ryzen 9 3900X, RTX 4080 SUPER, and 64GB RAM are ideal for running multiple LLMs concurrently.


## Next Steps (When Ready)

- Draft specific Telegram bot commands and interaction flows.
- Build minimal bot prototype for character sheet management and basic DM interaction.
- Iterate by adding system setups, dice rolling, and multi-topic gameplay.
- Expand to full story/narrative generation using fine-tuned and combined LLM models.

***

This setup leverages the power and accessibility of Telegram while utilizing advanced LLMs locally to create a rich, immersive tabletop RPG experience privately shared with friends.

If needed, assistance can be provided with development planning, code examples, or environment setup anytime.

***

This summary wraps up the project concept and progress so far in a way that’s easy to understand and reference later.
<span style="display:none">[^6_1][^6_2][^6_3][^6_4][^6_5][^6_6][^6_7][^6_8][^6_9]</span>

<div style="text-align: center">⁂</div>

[^6_1]: https://core.telegram.org

[^6_2]: https://www.reddit.com/r/Telegram/comments/1iy2ret/is_there_a_way_to_implement_channels_to/

[^6_3]: https://github.com/telegramdesktop/tdesktop/issues/5593

[^6_4]: https://www.youtube.com/watch?v=9ctV3uCY1II

[^6_5]: https://community.latenode.com/t/creating-a-text-based-rpg-telegram-bot-with-roguelike-mechanics/20658

[^6_6]: https://core.telegram.org/methods

[^6_7]: https://forum.scriptcase.net/t/scriptcase-users-supergroup-on-telegram/28844

[^6_8]: https://github.com/ebertti/awesome-telegram

[^6_9]: https://www.youtube.com/watch?v=HqKGB0-oHmQ


---

# Now the million dollar question...

has anyone done this before?

Yes, similar projects have been done before, though mostly in varying scopes and on different platforms. Here's a snapshot of relevant precedents:

- **Telegram AI Dungeon Bots:**
    - There are Telegram bots like "ai-dungeon-bot" (GitHub: sasha00123/ai-dungeon-bot) that run AI dungeon-style interactive storytelling using AI and support translations[^7_1].
    - The open-source "Pilgram" is a Telegram text-based idle MMO RPG powered by AI with multiplayer and quest generation[^7_2].
    - Other Telegram RPG bots exist, e.g., "LuisTessaro/RPG-Telegram-bot," focused on text-based dungeon crawling with multiplayer features[^7_3].
    - Some RPG helper bots manage character sheets and dice rolls but require a human gamemaster[^7_4].
- **Discord AI Dungeon Master Bots:**
    - "AI-Dungeon-Master-Discord-Bot" (GitHub: Hairenstein-Bear) runs AI-powered NPC generation and some DM features via Discord, though still early and experimental[^7_5][^7_6].
    - Commercial and community projects like Fables.gg running AI DMs on Discord with multiplayer support exist as well[^7_7].
- **General AI RPG Bots:**
    - Many implementations use GPT-3.5 or GPT-4 APIs, either hosted on cloud or local setups for AI Dungeon or similar gameplay.
    - Bots often combine story narration, dice rolling, character management, and AI NPCs to varying levels of complexity.


### Summary

> The idea of using Telegram supergroups, LLMs for AI DM, character/topic segmentation, and multilingual support is largely novel in scope and complexity, but it draws from and improves on multiple notable predecessors and open-source bots. None appear to fully match your envisioned feature set with local LLM hosting, advanced Telegram topic use, and bilingual language pipeline.

Your concept places strong emphasis on:

- Topic-separated in- vs out-of-character play
- LLM-powered storytelling with system-specific rules (D\&D/d20, WoD/d10, BESM)
- Dynamic NPC generation coupled with persistently stored NPCs
- Greek/English bilingual play with local model orchestration
- Full Telegram ecosystem integration with message and command flow

All this combined makes your project fairly unique and an excellent frontier to innovate and build with existing tools as a foundation.

When ready, I can help identify reusable bot codebases to fork or guide you in building it from the ground up.

If you'd like, I can also help analyze specific existing projects or libraries to speed up your development.
<span style="display:none">[^7_10][^7_11][^7_12][^7_13][^7_8][^7_9]</span>

<div style="text-align: center">⁂</div>

[^7_1]: https://github.com/sasha00123/ai-dungeon-bot

[^7_2]: https://www.reddit.com/r/MobileGaming/comments/1dj2gkd/ive_made_a_multiplayer_infinite_idle_rpg_game_on/

[^7_3]: https://github.com/LuisTessaro/RPG-Telegram-bot

[^7_4]: https://github.com/simonebaracchi/rpgbot

[^7_5]: https://github.com/Hairenstein-Bear/AI-Dungeon-Master-Discord-Bot

[^7_6]: https://github.com/samvoisin/ai-dungeon-master

[^7_7]: https://www.reddit.com/r/dndnext/comments/129igff/we_just_built_an_aipowered_dungeon_master_bot/

[^7_8]: https://github.com/theepicflyer/DnDBot

[^7_9]: https://aidungeon.com

[^7_10]: https://telegramic.org/bot/dungonbot/

[^7_11]: https://theresanaiforthat.com/s/dungeon+master/

[^7_12]: https://www.reddit.com/r/Python/comments/1e8pt2b/pilgram_a_texting_based_idle_mmo_rpg/

[^7_13]: https://community.latenode.com/t/creating-a-text-based-rpg-telegram-bot-with-roguelike-mechanics/20658

