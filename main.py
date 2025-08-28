import discord
from discord.ext import commands
import os
import asyncio
from aiohttp import web
from dotenv import load_dotenv
import base64
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
from cryptography.hazmat.backends import default_backend
from cryptography.hazmat.primitives import padding
import glob
import importlib.util
import sys

# Configurar logging para hacer el bot silencioso pero mostrar errores importantes
import logging
logging.getLogger('discord').setLevel(logging.ERROR)
logging.getLogger('discord.http').setLevel(logging.ERROR)
logging.getLogger('discord.gateway').setLevel(logging.ERROR)

# Configurar nuestro logger personalizado
logger = logging.getLogger('bot')
logger.setLevel(logging.INFO)
handler = logging.StreamHandler()
handler.setFormatter(logging.Formatter('%(asctime)s:%(levelname)s:%(name)s: %(message)s'))
logger.addHandler(handler)

# Función para obtener la clave de encriptación
def get_encryption_key():
    """Obtiene y deriva la clave desde la variable de entorno KEY_CODE"""
    try:
        key_code = os.environ.get('KEY_CODE')
        if not key_code:
            raise ValueError("KEY_CODE no está definida en las variables de entorno")
        
        # Decodifica la clave base64
        key = base64.urlsafe_b64decode(key_code)
        
        # Aseguramos que tenga exactamente 32 bytes
        if len(key) != 32:
            # Si no es exactamente 32 bytes, derivamos una clave usando PBKDF2
            salt = b'fixed_salt_for_github'
            kdf = PBKDF2HMAC(
                algorithm=hashes.SHA256(),
                length=32,
                salt=salt,
                iterations=100000,
                backend=default_backend()
            )
            key = kdf.derive(key_code.encode())
        
        return key
    except Exception as e:
        logger.error(f"Error getting encryption key: {e}")
        return None

# Función para desencriptar archivos
def decrypt_file(encrypted_content, key):
    """Descifra contenido usando AES-256 en modo CBC"""
    try:
        # Decodifica de Base64 a bytes
        encrypted_data = base64.b64decode(encrypted_content)
        
        # Separa el IV y el ciphertext
        iv = encrypted_data[:16]
        ciphertext = encrypted_data[16:]
        
        # Configura el descifrador
        cipher = Cipher(
            algorithms.AES(key),
            modes.CBC(iv),
            backend=default_backend()
        )
        decryptor = cipher.decryptor()
        
        # Descifra el contenido
        padded_plaintext = decryptor.update(ciphertext) + decryptor.finalize()
        
        # Elimina el padding
        unpadder = padding.PKCS7(128).unpadder()
        plaintext = unpadder.update(padded_plaintext) + unpadder.finalize()
        
        return plaintext.decode('utf-8')
    except Exception as e:
        logger.error(f"Error decrypting file: {e}")
        return None

# Función para verificar y desencriptar scripts
def decrypt_scripts():
    """Verifica y desencripta todos los scripts encriptados en el repositorio"""
    decrypted_files = []
    try:
        key = get_encryption_key()
        if not key:
            logger.error("No se pudo obtener la clave de encriptación")
            return decrypted_files
            
        # Buscar archivos con extensión .encrypted
        encrypted_files = glob.glob("**/*.encrypted", recursive=True)
        logger.info(f"Archivos encriptados encontrados: {encrypted_files}")
        
        for file_path in encrypted_files:
            # Evitar desencriptar el archivo principal si también está encriptado
            if file_path == os.path.basename(__file__):
                continue
                
            try:
                with open(file_path, 'r', encoding='utf-8') as file:
                    content = file.read()
                
                # Intentar desencriptar
                decrypted_content = decrypt_file(content, key)
                
                # Si la desencriptación fue exitosa, sobrescribir el archivo
                if decrypted_content is not None:
                    # Crear nuevo nombre de archivo sin la extensión .encrypted
                    new_path = file_path.replace('.encrypted', '')
                    with open(new_path, 'w', encoding='utf-8') as file:
                        file.write(decrypted_content)
                    
                    # Eliminar el archivo encriptado original
                    os.remove(file_path)
                    decrypted_files.append(new_path)
                    logger.info(f"Archivo desencriptado exitosamente: {file_path} -> {new_path}")
                else:
                    logger.error(f"No se pudo desencriptar: {file_path}")
                    
            except Exception as e:
                logger.error(f"Error procesando archivo {file_path}: {e}")
                
    except Exception as e:
        logger.error(f"Error en decrypt_scripts: {e}")
    
    return decrypted_files

# Ejecutar desencriptación antes de continuar
decrypted = decrypt_scripts()
logger.info(f"Archivos desencriptados: {len(decrypted)}")

load_dotenv()

# Configurar intents con todos los necesarios
intents = discord.Intents.default()
intents.message_content = True
intents.members = True
intents.guilds = True

# Decorador para requerir roles permitidos, si se definen
def require_roles(allowed_roles=None):
    def decorator(func):
        async def predicate(ctx, *args, **kwargs):
            if allowed_roles is None:
                return await func(ctx, *args, **kwargs)
            user_roles = [r.name for r in ctx.author.roles]
            if any(role in user_roles for role in allowed_roles):
                return await func(ctx, *args, **kwargs)
            await ctx.send("No tienes permisos para usar este comando.")
            return
        return commands.check(lambda ctx: allowed_roles is None or any(role.name in allowed_roles for role in ctx.author.roles))(func)
    return decorator

class SilentBot(commands.Bot):
    def __init__(self):
        super().__init__(
            command_prefix='!',
            intents=intents,
            help_command=None
        )
        self.loaded_cogs = set()
        self.cog_guilds = {}  # {cog_name: [guild_ids] or None}
        self.cog_roles = {}   # {cog_name: [roles] or None}
    
    async def load_cog_safely(self, cog_name, module_path):
        """Carga un cog de manera segura, evitando duplicados, y guarda guilds y roles"""
        if cog_name in self.loaded_cogs:
            logger.warning(f"El cog {cog_name} ya estaba cargado, omitiendo")
            return False
        
        try:
            # Cargar el módulo manualmente para leer variables
            spec = importlib.util.spec_from_file_location(cog_name, module_path)
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)
            allowed_guilds = getattr(module, "ALLOWED_GUILDS", None)
            allowed_roles = getattr(module, "ALLOWED_ROLES", None)
            self.cog_guilds[cog_name] = allowed_guilds
            self.cog_roles[cog_name] = allowed_roles

            await self.load_extension(cog_name)
            self.loaded_cogs.add(cog_name)
            logger.info(f"Cog cargado: {cog_name}")
            return True
        except commands.ExtensionAlreadyLoaded:
            logger.warning(f"El cog {cog_name} ya estaba cargado")
            self.loaded_cogs.add(cog_name)
            return True
        except commands.ExtensionNotFound:
            logger.error(f"El cog {cog_name} no se encontró")
            return False
        except commands.ExtensionFailed as e:
            logger.error(f"Error al cargar el cog {cog_name}: {e}")
            return False
        except Exception as e:
            logger.error(f"Error inesperado al cargar el cog {cog_name}: {e}")
            return False
    
    async def setup_hook(self):
        # Cargar todos los comandos de la carpeta commands
        await self.load_all_cogs()
        
        # Sincronizar comandos por guild o global según corresponda
        for cog_name, allowed_guilds in self.cog_guilds.items():
            if allowed_guilds:
                for guild_id in allowed_guilds:
                    try:
                        guild = discord.Object(id=guild_id)
                        synced = await self.tree.sync(guild=guild)
                        logger.info(f"Comandos {cog_name} sincronizados solo en guild {guild_id}: {len(synced)}")
                    except Exception as e:
                        logger.error(f"Error al sincronizar {cog_name} para guild {guild_id}: {e}")
            else:
                try:
                    synced = await self.tree.sync()
                    logger.info(f"Comandos {cog_name} sincronizados globalmente: {len(synced)}")
                except Exception as e:
                    logger.error(f"Error al sincronizar {cog_name} global: {e}")

    async def load_all_cogs(self):
        """Carga todos los cogs de la carpeta commands y lee sus restricciones"""
        if not os.path.exists('./commands'):
            logger.warning("No se encontró el directorio commands")
            return
            
        for filename in os.listdir('./commands'):
            if filename.endswith('.py') and filename != '__init__.py':
                cog_name = f'commands.{filename[:-3]}'
                module_path = os.path.join('./commands', filename)
                await self.load_cog_safely(cog_name, module_path)

bot = SilentBot()

async def web_server():
    app = web.Application()
    app.router.add_get('/', lambda request: web.Response(text="Bot is running!"))
    runner = web.AppRunner(app)
    await runner.setup()
    port = int(os.environ.get('PORT', 10000))
    site = web.TCPSite(runner, host='0.0.0.0', port=port)
    await site.start()

@bot.event
async def on_ready():
    logger.info(f'Conectado como {bot.user} (ID: {bot.user.id})')
    
    # Configurar estado personalizado
    status_type = os.getenv('STATUS', 'online').lower()
    activity_type = os.getenv('ACTIVITY_TYPE', 'none').lower()
    activity_name = os.getenv('ACTIVITY_NAME', 'Default Activity')

    # Mapear tipos de actividad
    activity_dict = {
        'playing': discord.ActivityType.playing,
        'streaming': discord.ActivityType.streaming,
        'listening': discord.ActivityType.listening,
        'watching': discord.ActivityType.watching,
        'competing': discord.ActivityType.competing,
        'none': None
    }

    # Mapear estados
    status_dict = {
        'online': discord.Status.online,
        'dnd': discord.Status.dnd,
        'idle': discord.Status.idle,
        'offline': discord.Status.offline,
        'invisible': discord.Status.invisible
    }

    # Configurar actividad (o ninguna)
    if activity_type == 'none':
        activity = None
    else:
        activity = discord.Activity(
            type=activity_dict.get(activity_type, discord.ActivityType.playing),
            name=activity_name
        )

    # Establecer el estado personalizado
    await bot.change_presence(
        activity=activity,
        status=status_dict.get(status_type, discord.Status.online)
    )

    # Iniciar el servidor web
    asyncio.create_task(web_server())

# Manejar errores de comandos
@bot.event
async def on_command_error(ctx, error):
    if isinstance(error, commands.CommandNotFound):
        return  # Ignorar comandos no encontrados
    logger.error(f"Error en comando {getattr(ctx.command, 'name', 'desconocido')}: {error}")

# Ejecutar el bot
token = os.getenv('DISCORD_TOKEN')
if token:
    bot.run(token)
else:
    logger.error("DISCORD_TOKEN no encontrado en las variables de entorno")
    exit("Token no encontrado")
