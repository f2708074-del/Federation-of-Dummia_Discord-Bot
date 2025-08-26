import discord
from discord.ext import commands
from discord import app_commands
from discord.ui import Button, View, Modal, TextInput
import logging
from supabase import create_client, Client
import os

# -------------------- Restricciones para este script --------------------
ALLOWED_GUILDS = [1363452931747086456]
ALLOWED_ROLES = [1409865894217126048]

# Configure logging for this cog
logger = logging.getLogger('points_system')

# Configuración de Supabase
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")
supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

# -------------------- Funciones de Base de Datos --------------------
async def get_user_points(user_id: int, guild_id: int) -> int:
    """Obtener los puntos de un usuario"""
    try:
        response = supabase.table("federation_of_dummia_user_points").select("points").eq("user_id", str(user_id)).eq("guild_id", str(guild_id)).execute()
        if response.data:
            return response.data[0]["points"]
        else:
            # Si no existe, crear registro con 0 puntos
            supabase.table("federation_of_dummia_user_points").insert({
                "user_id": str(user_id),
                "guild_id": str(guild_id),
                "points": 0
            }).execute()
            return 0
    except Exception as e:
        logger.error(f"Error getting user points: {e}")
        return 0

async def update_user_points(user_id: int, guild_id: int, points: int) -> bool:
    """Actualizar los puntos de un usuario (suma/resta)"""
    try:
        current_points = await get_user_points(user_id, guild_id)
        new_points = current_points + points
        
        supabase.table("federation_of_dummia_user_points").upsert({
            "user_id": str(user_id),
            "guild_id": str(guild_id),
            "points": new_points
        }).execute()
        return True
    except Exception as e:
        logger.error(f"Error updating user points: {e}")
        return False

async def set_user_points(user_id: int, guild_id: int, points: int) -> bool:
    """Establecer los puntos de un usuario (valor absoluto)"""
    try:
        supabase.table("federation_of_dummia_user_points").upsert({
            "user_id": str(user_id),
            "guild_id": str(guild_id),
            "points": points
        }).execute()
        return True
    except Exception as e:
        logger.error(f"Error setting user points: {e}")
        return False

# -------------------- Role Verification --------------------
def require_roles():
    """Decorator to verify the user has at least one of the allowed roles in the guild"""
    async def predicate(interaction: discord.Interaction) -> bool:
        if not interaction.guild:
            await interaction.response.send_message("This command can only be used in a server.", ephemeral=True)
            return False
        
        guild_id = interaction.guild.id
        if guild_id not in ALLOWED_GUILDS:
            await interaction.response.send_message("This command is not available in this server.", ephemeral=True)
            return False
        
        member = interaction.user
        has_allowed_role = any(role.id in ALLOWED_ROLES for role in member.roles)
        
        if not has_allowed_role:
            role_mentions = [f"<@&{role_id}>" for role_id in ALLOWED_ROLES]
            await interaction.response.send_message(
                f"You don't have the required roles to use this command. You need one of: {', '.join(role_mentions)}",
                ephemeral=True
            )
            return False
            
        return True
    return app_commands.check(predicate)

# -------------------- Modals para puntos --------------------
class ManagePointsModal(Modal, title="Manage Points"):
    def __init__(self, user_id: int, guild_id: int):
        super().__init__()
        self.user_id = user_id
        self.guild_id = guild_id
        self.points = TextInput(
            label="Points to add/subtract",
            placeholder="Enter a positive or negative number...",
            style=discord.TextStyle.short,
            required=True
        )
        self.add_item(self.points)

    async def on_submit(self, interaction: discord.Interaction):
        try:
            points_change = int(self.points.value)
            success = await update_user_points(self.user_id, self.guild_id, points_change)
            
            if success:
                new_points = await get_user_points(self.user_id, self.guild_id)
                await interaction.response.send_message(
                    f"Points updated successfully. New total: {new_points}", 
                    ephemeral=True
                )
            else:
                await interaction.response.send_message(
                    "Error updating points. Please try again.", 
                    ephemeral=True
                )
        except ValueError:
            await interaction.response.send_message(
                "Please enter a valid number.", 
                ephemeral=True
            )

class SetPointsModal(Modal, title="Set Points"):
    def __init__(self, user_id: int, guild_id: int):
        super().__init__()
        self.user_id = user_id
        self.guild_id = guild_id
        self.points = TextInput(
            label="New points value",
            placeholder="Enter the new points value...",
            style=discord.TextStyle.short,
            required=True
        )
        self.add_item(self.points)

    async def on_submit(self, interaction: discord.Interaction):
        try:
            new_points = int(self.points.value)
            success = await set_user_points(self.user_id, self.guild_id, new_points)
            
            if success:
                await interaction.response.send_message(
                    f"Points set successfully to {new_points}.", 
                    ephemeral=True
                )
            else:
                await interaction.response.send_message(
                    "Error setting points. Please try again.", 
                    ephemeral=True
                )
        except ValueError:
            await interaction.response.send_message(
                "Please enter a valid number.", 
                ephemeral=True
            )

# -------------------- View con botones --------------------
class PointsView(View):
    def __init__(self, user_id: int, guild_id: int):
        super().__init__(timeout=180)  # Timeout de 3 minutos
        self.user_id = user_id
        self.guild_id = guild_id

    @discord.ui.button(label="Manage Points", style=discord.ButtonStyle.primary, emoji="⚙️")
    async def manage_points(self, interaction: discord.Interaction, button: Button):
        # Verificar roles
        if not any(role.id in ALLOWED_ROLES for role in interaction.user.roles):
            await interaction.response.send_message(
                "You don't have permission to manage points.", 
                ephemeral=True
            )
            return
            
        await interaction.response.send_modal(ManagePointsModal(self.user_id, self.guild_id))

    @discord.ui.button(label="Set up Points", style=discord.ButtonStyle.secondary, emoji="💯")
    async def set_points(self, interaction: discord.Interaction, button: Button):
        # Verificar roles
        if not any(role.id in ALLOWED_ROLES for role in interaction.user.roles):
            await interaction.response.send_message(
                "You don't have permission to set points.", 
                ephemeral=True
            )
            return
            
        await interaction.response.send_modal(SetPointsModal(self.user_id, self.guild_id))

# -------------------- Cog principal --------------------
class PointsSystem(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.logger = logging.getLogger('points_system')

    @app_commands.command(name="mypoints", description="Check your points")
    @app_commands.guilds(discord.Object(id=1363452931747086456))  # Solo el guild permitido
    async def mypoints(self, interaction: discord.Interaction):
        try:
            user_id = interaction.user.id
            guild_id = interaction.guild.id
            
            # Obtener puntos del usuario
            points = await get_user_points(user_id, guild_id)
            
            # Crear embed
            embed = discord.Embed(
                title=f"Points for {interaction.user.display_name}",
                description=f"You have **{points}** points.",
                color=discord.Color.blue()
            )
            embed.set_thumbnail(url=interaction.user.avatar.url)
            
            # Crear vista con botones
            view = PointsView(user_id, guild_id)
            
            await interaction.response.send_message(embed=embed, view=view)
            
        except Exception as e:
            self.logger.error(f"Error in mypoints command: {e}")
            await interaction.response.send_message(
                "An error occurred while fetching your points.",
                ephemeral=True
            )

async def setup(bot: commands.Bot):
    await bot.add_cog(PointsSystem(bot))
    logger.info("PointsSystem cog loaded successfully")
