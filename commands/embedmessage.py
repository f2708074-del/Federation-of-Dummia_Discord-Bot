import discord
from discord.ext import commands
from discord import app_commands
from discord.ui import Modal, TextInput
import logging

# Configuración de permisos
ALLOWED_GUILDS = [1363452931747086456]  # Reemplaza con tu ID de servidor
ALLOWED_ROLES = [1409865894217126048]   # Reemplaza con tu ID de rol

# Configurar logging
logger = logging.getLogger('embed_creator')

# Verificación de roles
def require_roles():
    async def predicate(interaction: discord.Interaction) -> bool:
        if not interaction.guild:
            await interaction.response.send_message("Este comando solo puede usarse en un servidor.", ephemeral=True)
            return False
        
        member_roles = [role.id for role in interaction.user.roles]
        has_allowed_role = any(role_id in member_roles for role_id in ALLOWED_ROLES)
        
        if not has_allowed_role:
            await interaction.response.send_message(
                f"No tienes los roles necesarios para usar este comando.",
                ephemeral=True
            )
            return False
            
        return True
    return app_commands.check(predicate)

# Modal para crear el embed
class EmbedModal(Modal, title="Crear Embed Personalizado"):
    def __init__(self, channel: discord.TextChannel):
        super().__init__()
        self.channel = channel
        
        self.embed_title = TextInput(
            label="Título del Embed",
            placeholder="Ingresa el título aquí...",
            style=discord.TextStyle.short,
            required=False,
            max_length=256
        )
        
        self.embed_description = TextInput(
            label="Descripción del Embed",
            placeholder="Ingresa la descripción aquí...",
            style=discord.TextStyle.paragraph,
            required=True
        )
        
        self.embed_color = TextInput(
            label="Color (Hex o nombre)",
            placeholder="#FF0000 o red",
            style=discord.TextStyle.short,
            required=False,
            max_length=20
        )
        
        self.embed_footer = TextInput(
            label="Pie de página",
            placeholder="Texto para el footer...",
            style=discord.TextStyle.short,
            required=False,
            max_length=2048
        )
        
        self.add_item(self.embed_title)
        self.add_item(self.embed_description)
        self.add_item(self.embed_color)
        self.add_item(self.embed_footer)

    async def on_submit(self, interaction: discord.Interaction):
        try:
            # Crear embed
            embed = discord.Embed(
                title=self.embed_title.value if self.embed_title.value else None,
                description=self.embed_description.value,
                color=discord.Color.default()
            )
            
            # Procesar color
            if self.embed_color.value:
                try:
                    if self.embed_color.value.startswith('#'):
                        embed.color = discord.Color(int(self.embed_color.value[1:], 16))
                    else:
                        embed.color = discord.Color.from_str(self.embed_color.value.lower())
                except:
                    embed.color = discord.Color.default()
            
            # Añadir footer si existe
            if self.embed_footer.value:
                embed.set_footer(text=self.embed_footer.value)
            
            # Enviar al canal especificado
            await self.channel.send(embed=embed)
            
            await interaction.response.send_message(
                f"¡Embed enviado exitosamente a {self.channel.mention}!",
                ephemeral=True
            )
            
        except Exception as e:
            logger.error(f"Error creating embed: {e}")
            await interaction.response.send_message(
                "Ocurrió un error al crear el embed.",
                ephemeral=True
            )

# Cog principal
class EmbedCreator(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @app_commands.command(name="crear-embed", description="Crea un embed personalizado en el canal especificado")
    @app_commands.guilds(*ALLOWED_GUILDS)
    @require_roles()
    @app_commands.describe(channel="Canal donde enviar el embed")
    async def crear_embed(self, interaction: discord.Interaction, channel: discord.TextChannel):
        modal = EmbedModal(channel)
        await interaction.response.send_modal(modal)

async def setup(bot: commands.Bot):
    await bot.add_cog(EmbedCreator(bot))
    logger.info("EmbedCreator cog loaded successfully")
