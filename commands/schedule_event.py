import discord
from discord.ext import commands
from discord import app_commands
from discord.ui import Button, View, Modal, TextInput
import random
import logging
import traceback
from typing import Optional, Dict

logger = logging.getLogger("schedule_event")

# Configura estos IDs según tu servidor
REQUIRED_ROLE_ID = 1409570130626871327  # Rol requerido para usar el comando
GUILD_ID = 1365324373094957146          # ID de tu servidor

# Almacenamiento en memoria de eventos
events: Dict[int, dict] = {}

# -------------------- Verificación de rol --------------------
def require_role():
    async def predicate(interaction: discord.Interaction) -> bool:
        if not interaction.guild:
            return False
        member = interaction.user
        role = interaction.guild.get_role(REQUIRED_ROLE_ID)
        return bool(role and role in member.roles)
    return app_commands.check(predicate)

# -------------------- Modal y Views --------------------
class EventCancelModal(Modal, title="Close Event"):
    def __init__(self, event_id: int):
        super().__init__()
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
        event = events.get(self.event_id)
        if not event:
            await interaction.response.send_message("Event not found.", ephemeral=True)
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

class EndEventView(View):
    def __init__(self, event_id: int, event_type: str):
        super().__init__(timeout=None)
        self.event_id = event_id
        self.event_type = event_type

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        role = interaction.guild.get_role(REQUIRED_ROLE_ID)
        return role in interaction.user.roles

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
        event = events.get(self.event_id)
        if not event:
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

class EventManageView(View):
    def __init__(self, event_id: int, event_type: str):
        super().__init__(timeout=None)
        self.event_id = event_id
        self.event_type = event_type

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        role = interaction.guild.get_role(REQUIRED_ROLE_ID)
        return role in interaction.user.roles

    @discord.ui.button(label="Cancel Event", style=discord.ButtonStyle.danger)
    async def cancel_event(self, interaction: discord.Interaction, button: Button):
        await interaction.response.send_modal(EventCancelModal(self.event_id))

    @discord.ui.button(label="Start Event", style=discord.ButtonStyle.success)
    async def start_event(self, interaction: discord.Interaction, button: Button):
        event = events.get(self.event_id)
        if not event:
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

    @discord.ui.button(label="End Event", style=discord.ButtonStyle.primary)
    async def end_event(self, interaction: discord.Interaction, button: Button):
        await interaction.response.send_message(
            "How did the event end?",
            view=EndEventView(self.event_id, self.event_type),
            ephemeral=True
        )

class EventButton(View):
    def __init__(self, event_id: int, event_type: str):
        super().__init__(timeout=None)
        self.event_id = event_id
        self.event_type = event_type

    @discord.ui.button(emoji="⚙️", style=discord.ButtonStyle.secondary)
    async def manage_event(self, interaction: discord.Interaction, button: Button):
        role = interaction.guild.get_role(REQUIRED_ROLE_ID)
        if role not in interaction.user.roles:
            await interaction.response.send_message("Missing permissions.", ephemeral=True)
            return

        await interaction.response.send_message(
            "Manage Event Options:",
            view=EventManageView(self.event_id, self.event_type),
            ephemeral=True
        )

# -------------------- Cog principal --------------------
class ScheduleEvent(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @app_commands.command(name="schedule-event", description="Schedule a new event")
    @app_commands.guilds(discord.Object(id=GUILD_ID))
    @require_role()
    @app_commands.describe(
        channel="Channel to send the event message",
        event_type="Type of event",
        host="Host of the event",
        time="Time (e.g., <t:1620000000:R>)",
        duration="Duration",
        place="Place",
        notes="Notes (optional)"
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
        notes: Optional[str] = None
    ):
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

    async def cog_app_command_error(self, interaction: discord.Interaction, error: app_commands.AppCommandError):
        if isinstance(error, app_commands.CheckFailure):
            await interaction.response.send_message(
                "You don't have permission to use this command.",
                ephemeral=True
            )

async def setup(bot: commands.Bot):
    await bot.add_cog(ScheduleEvent(bot))
