import os
import discord
from discord.ext import commands
from google.cloud import translate_v2 as translate
from dotenv import load_dotenv
from langdetect import detect, LangDetectException
import json
from collections import defaultdict
import traceback
from datetime import datetime

# Cargar variables de entorno
load_dotenv()

# Configuración
SOURCE_LANGUAGES = os.getenv('SOURCE_LANGUAGES', 'it,es').split(',')
TARGET_LANGUAGE_IT = os.getenv('TARGET_LANGUAGE_IT', 'es')
TARGET_LANGUAGE_ES = os.getenv('TARGET_LANGUAGE_ES', 'it')
LEARNING_MODE = os.getenv('LEARNING_MODE', 'true').lower() == 'true'

# Banderas
BANDERAS = {'es': '🇪🇸', 'it': '🇮🇹'}

# Manejo seguro de ADMIN_USER_IDS
def parse_user_ids(id_string):
    if not id_string:
        return []
    try:
        return [int(id.strip()) for id in id_string.split(',') if id.strip().isdigit()]
    except ValueError:
        return []

ADMIN_USER_IDS = parse_user_ids(os.getenv('ADMIN_USER_IDS'))

# Cliente de traducción
translate_client = translate.Client()

# Cargar diccionarios
def load_dictionaries():
    dictionaries = {}
    dict_files = {
        'gaming': 'gaming_es_it.json',
        'sex': 'sex_es_it.json',
        'colloquial': 'colloquial_es_it.json'
    }
    
    for category, file_path in dict_files.items():
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                dictionaries[category] = json.load(f)
        except (FileNotFoundError, json.JSONDecodeError):
            dictionaries[category] = {'es': {}, 'it': {}}
    
    return dictionaries

# Cargar sugerencias
def load_user_suggestions():
    try:
        with open('user_suggestions.json', 'r', encoding='utf-8') as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return defaultdict(list)

# Guardar sugerencias
def save_user_suggestions(suggestions):
    with open('user_suggestions.json', 'w', encoding='utf-8') as f:
        json.dump(suggestions, f, ensure_ascii=False, indent=2)

# Inicializar datos
custom_dictionaries = load_dictionaries()
user_suggestions = load_user_suggestions()

# Crear bot
intents = discord.Intents.default()
intents.messages = True
intents.message_content = True

bot = commands.Bot(command_prefix='!', intents=intents)

# Detección de idioma
def detect_language(text):
    if not text or len(text.strip()) < 3:
        return None
    try:
        return detect(text) if detect(text) in SOURCE_LANGUAGES else None
    except LangDetectException:
        return None

# Traducción preservando saltos
async def translate_preserving_newlines(text, source_lang, target_lang):
    # Dividir por líneas
    lines = text.split('\n')
    translated_lines = []
    
    for line in lines:
        if line.strip():  # Solo traducir líneas con contenido
            try:
                # Buscar en diccionarios primero
                for category in custom_dictionaries.values():
                    if source_lang in category and target_lang in category[source_lang]:
                        if line.lower() in category[source_lang][target_lang]:
                            translated_lines.append(category[source_lang][target_lang][line.lower()])
                            continue
                
                # Traducción automática
                result = translate_client.translate(
                    line,
                    source_language=source_lang,
                    target_language=target_lang
                )
                translated_lines.append(result['translatedText'])
            except Exception:
                translated_lines.append(line)  # Mantener original si falla
        else:
            translated_lines.append('')  # Conservar línea vacía
    
    return '\n'.join(translated_lines)

# Evento ready
@bot.event
async def on_ready():
    print(f'Bot listo: {bot.user}')

# Manejo de mensajes
@bot.event
async def on_message(message):
    if message.author == bot.user:
        return

    try:
        source_lang = detect_language(message.content)
        if source_lang:
            target_lang = TARGET_LANGUAGE_IT if source_lang == 'it' else TARGET_LANGUAGE_ES
            translated = await translate_preserving_newlines(message.content, source_lang, target_lang)
            
            # Formatear respuesta preservando saltos
            response = (
                f"{BANDERAS[source_lang]}→{BANDERAS[target_lang]}:\n"
                f"{translated}"
            )
            
            # Dividir mensajes largos (Discord limita a 2000 caracteres)
            if len(response) > 1900:
                parts = [response[i:i+1900] for i in range(0, len(response), 1900)]
                for part in parts:
                    await message.channel.send(part)
            else:
                await message.channel.send(response)
    
    except Exception as e:
        print(f"Error: {traceback.format_exc()}")
        await message.channel.send("⚠️ Error al procesar la traducción")

    await bot.process_commands(message)

# Comandos (opcional)
@bot.command()
async def ping(ctx):
    await ctx.send('Pong! Latencia: {0}ms'.format(round(bot.latency * 1000, 1)))

# Ejecutar bot
if __name__ == '__main__':
    bot.run(os.getenv('DISCORD_TOKEN'))
