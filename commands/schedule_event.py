import discord
from discord.ext import commands
from discord import app_commands
from discord.ui import Button, View, Modal, TextInput
import random
import logging
import traceback
from typing import Optional, Dict

logger = logging.getLogger("schedule_event")

# Ajusta estos IDs a tu servidor / rol si es necesario
REQUIRED_ROLE_ID = 1409570130626871327
GUILD_ID = 1365324373094957146

# Almacenamiento en memoria (no persistente)
events: Dict[int, dict] = {}

# -------------------- Check para role específico --------------------
def require_role():
    """Decorator que exige que el invocador tenga el rol REQUIRED_ROLE_ID."""
    async def predicate(interaction: discord.Interaction) -> bool:
        # Solo válido en guild (no en DMs)
        if not interaction.guild:
            return False
        member: Optional[discord.Member] = interaction.user  # in guild context this is Member
        role = interaction.guild.get_role(REQUIRED_ROLE_ID)
        return bool(role and role in getattr(member, "roles", []))
    return app_commands.check(predicate)

# -------------------- Modal y Views --------------------
class EventCancelModal(Modal):
    def __init__(self, event_id: int):
        super().__init__(title="Close Event")
        self.event_id = event_id
        self.reason = TextInput(
            label="Close reason",
            placeholder="Enter the reason for cancellation...",
            style=discord.TextStyle.paragraph,
            required=True,
            max_length=200
        )
        self.add_item(self.reason)

    async def on_submit(self, interaction: discord.Interaction):
        try:
            event = events.get(self.event_id)
            if not event or not event["message"].embeds:
                await interaction.response.send_message("Event not found or malformed.", ephemeral=True)
                return

            embed = event["message"].embeds[0]
            new_embed = discord.Embed.from_dict(embed.to_dict())

            for i, field in enumerate(new_embed.fields):
                if field.name == "Status":
                    new_embed.set_field_at(i, name="Status", value=f"Cancelled — {self.reason.value}", inline=True)
                    break

            await event["message"].edit(embed=new_embed, view=None)
            events[self.event_id]["status"] = "Cancelled"
            await interaction.response.send_message("Event cancelled successfully.", ephemeral=True)
        except Exception:
            logger.error("EventCancelModal error:\n" + traceback.format_exc())
            try:
                await interaction.response.send_message("Error processing the modal.", ephemeral=True)
            except Exception:
                pass

class EndEventView(View):
    def __init__(self, event_id: int, event_type: str):
        super().__init__(timeout=None)
        self.event_id = event_id
        self.event_type = event_type

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        try:
            role = interaction.guild.get_role(REQUIRED_ROLE_ID) if interaction.guild else None
            member = interaction.user
            if not role or role not in getattr(member, "roles", []):
                await interaction.response.send_message("Missing permissions.", ephemeral=True)
                return False
            return True
        except Exception:
            return False

    @discord.ui.button(label="End Event", style=discord.ButtonStyle.secondary)
    async def simple_end(self, interaction: discord.Interaction, button: Button):
        await self.update_event_status(interaction, "Event Ended")

    @discord.ui.button(label="Event Won", style=discord.ButtonStyle.success)
    async def event_won(self, interaction: discord.Interaction, button: Button):
        await self.update_event_status(interaction, f"Event Ended | {self.event_type} won!")

    @discord.ui.button(label="Event Failed", style=discord.ButtonStyle.danger)
    async def event_failed(self, interaction: discord.Interaction, button: Button):
        await self.update_event_status(interaction, f"Event Ended | {self.event_type} failed!")

    async def update_event_status(self, interaction: discord.Interaction, status: str):
        try:
            event = events.get(self.event_id)
            if not event or not event["message"].embeds:
                await interaction.response.send_message("Event not found.", ephemeral=True)
                return

            embed = event["message"].embeds[0]
            new_embed = discord.Embed.from_dict(embed.to_dict())

            for i, field in enumerate(new_embed.fields):
                if field.name == "Status":
                    new_embed.set_field_at(i, name="Status", value=status, inline=True)
                    break

            await event["message"].edit(embed=new_embed, view=None)
            events[self.event_id]["status"] = status
            await interaction.response.send_message(f"Event status updated to: {status}", ephemeral=True)
        except Exception:
            logger.error("EndEventView.update_event_status error:\n" + traceback.format_exc())
            try:
                await interaction.response.send_message("Error updating status.", ephemeral=True)
            except Exception:
                pass

class EventManageView(View):
    def __init__(self, event_id: int, event_type: str):
        super().__init__(timeout=None)
        self.event_id = event_id
        self.event_type = event_type

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        try:
            role = interaction.guild.get_role(REQUIRED_ROLE_ID) if interaction.guild else None
            member = interaction.user
            if not role or role not in getattr(member, "roles", []):
                await interaction.response.send_message("Missing permissions.", ephemeral=True)
                return False
            return True
        except Exception:
            return False

    @discord.ui.button(label="Cancel Event", style=discord.ButtonStyle.danger)
    async def cancel_event(self, interaction: discord.Interaction, button: Button):
        try:
            await interaction.response.send_modal(EventCancelModal(self.event_id))
        except Exception:
            logger.error("EventManageView.cancel_event error:\n" + traceback.format_exc())
            try:
                await interaction.response.send_message("Error opening modal.", ephemeral=True)
            except Exception:
                pass

    @discord.ui.button(label="Start Event", style=discord.ButtonStyle.success)
    async def start_event(self, interaction: discord.Interaction, button: Button):
        try:
            event = events.get(self.event_id)
            if not event or not event["message"].embeds:
                await interaction.response.send_message("Event not found.", ephemeral=True)
                return

            embed = event["message"].embeds[0]
            new_embed = discord.Embed.from_dict(embed.to_dict())
            for i, field in enumerate(new_embed.fields):
                if field.name == "Status":
                    new_embed.set_field_at(i, name="Status", value="Ongoing Event", inline=True)
                    break

            await event["message"].edit(embed=new_embed)
            events[self.event_id]["status"] = "Ongoing"
            await interaction.response.send_message("Event started.", ephemeral=True)
        except Exception:
            logger.error("EventManageView.start_event error:\n" + traceback.format_exc())
            try:
                await interaction.response.send_message("Error starting event.", ephemeral=True)
            except Exception:
                pass

    @discord.ui.button(label="End Event", style=discord.ButtonStyle.primary)
    async def end_event(self, interaction: discord.Interaction, button: Button):
        try:
            await interaction.response.send_message("How did the event end?", view=EndEventView(self.event_id, self.event_type), ephemeral=True)
        except Exception:
            logger.error("EventManageView.end_event error:\n" + traceback.format_exc())
            try:
                await interaction.response.send_message("Error opening end-event view.", ephemeral=True)
            except Exception:
                pass

class EventButton(View):
    def __init__(self, event_id: int, event_type: str):
        super().__init__(timeout=None)
        self.event_id = event_id
        self.event_type = event_type

    @discord.ui.button(emoji="⚙️", style=discord.ButtonStyle.secondary)
    async def manage_event(self, interaction: discord.Interaction, button: Button):
        try:
            role = interaction.guild.get_role(REQUIRED_ROLE_ID) if interaction.guild else None
            member = interaction.user
            if not role or role not in getattr(member, "roles", []):
                await interaction.response.send_message("Missing permissions.", ephemeral=True)
                return

            await interaction.response.send_message("Manage Event Options:", view=EventManageView(self.event_id, self.event_type), ephemeral=True)
        except Exception:
            logger.error("EventButton.manage_event error:\n" + traceback.format_exc())
            try:
                await interaction.response.send_message("Error opening management options.", ephemeral=True)
            except Exception:
                pass

# -------------------- Cog con el slash command --------------------
class ScheduleEvent(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    # Aplica: 1) restriction al guild para registrar rápido, 2) require_role() para que solo el rol pueda ejecutarlo
    @app_commands.command(name="schedule-event", description="Schedule a new event")
    @app_commands.guilds(discord.Object(id=GUILD_ID))  # opcional pero recomendado para registro rápido en tu servidor
    @require_role()
    @app_commands.describe(
        channel="Channel to send the event message",
        event_type="Type of event",
        host="Host of the event",
        time="Time (p.ej. <t:1620000000:R>)",
        duration="Duration",
        place="Place",
        notes="Notes (opcional)"
    )
    @app_commands.choices(event_type=[
        app_commands.Choice(name="Test1", value="Test1"),
        app_commands.Choice(name="Test2", value="Test2")
    ])
    async def schedule_event(
        self,
        interaction: discord.Interaction,
        channel: discord.TextChannel,
        event_type: app_commands.Choice[str],
        host: discord.Member,
        time: str,
        duration: str,
        place: str,
        notes: str = None
    ):
        try:
            # Ya comprobado por el check, pero hacemos una verificación extra por seguridad
            role = interaction.guild.get_role(REQUIRED_ROLE_ID) if interaction.guild else None
            if not role or role not in getattr(interaction.user, "roles", []):
                await interaction.response.send_message("Missing permissions.", ephemeral=True)
                return

            event_id = random.randint(10000, 99999)
            while event_id in events:
                event_id = random.randint(10000, 99999)

            embed = discord.Embed(
                title=f"Event: {event_type.name}",
                color=discord.Color.blue(),
                timestamp=discord.utils.utcnow()
            )
            embed.add_field(name="Host", value=host.mention, inline=True)
            embed.add_field(name="Time", value=time, inline=True)
            embed.add_field(name="Duration", value=duration, inline=True)
            embed.add_field(name="Place", value=place, inline=False)
            embed.add_field(name="Event Type", value=event_type.name, inline=True)
            if notes:
                embed.add_field(name="Notes", value=notes, inline=False)
            embed.add_field(name="Status", value="Scheduled", inline=True)
            embed.set_footer(text=f"Created by {interaction.user.display_name} • EventID: {event_id}")

            view = EventButton(event_id, event_type.name)
            message = await channel.send(embed=embed, view=view)

            events[event_id] = {
                "message": message,
                "channel": channel.id,
                "host": host.id,
                "type": event_type.name,
                "status": "Scheduled",
                "creator": interaction.user.id,
                "notes": notes
            }

            await interaction.response.send_message(f"Event scheduled! EventID: {event_id}", ephemeral=True)
        except Exception:
            logger.error("schedule_event error:\n" + traceback.format_exc())
            try:
                await interaction.response.send_message("Error scheduling event.", ephemeral=True)
            except Exception:
                pass

    # Manejo de errores para app_commands en el cog (notifica si falla el check)
    async def cog_app_command_error(self, interaction: discord.Interaction, error: app_commands.AppCommandError):
        if isinstance(error, app_commands.CheckFailure):
            try:
                await interaction.response.send_message("No tienes permisos para usar este comando (rol requerido).", ephemeral=True)
            except Exception:
                try:
                    await interaction.followup.send("No tienes permisos para usar este comando (rol requerido).", ephemeral=True)
                except Exception:
                    pass
        else:
            logger.error("Unhandled app command error:\n" + traceback.format_exc())
            try:
                await interaction.response.send_message("Ocurrió un error al ejecutar el comando.", ephemeral=True)
            except Exception:
                pass

# setup requerido por bot.load_extension
async def setup(bot: commands.Bot):
    await bot.add_cog(ScheduleEvent(bot))
