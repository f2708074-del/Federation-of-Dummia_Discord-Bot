import discord
from discord import app_commands
from discord.ui import Button, View, Modal, TextInput
import random
import os
from datetime import datetime

# Configuración con tus IDs
REQUIRED_ROLE_ID = 1409570130626871327  # Rol requerido
GUILD_ID = 1365324373094957146          # ID del servidor

intents = discord.Intents.default()
intents.members = True
intents.message_content = True

bot = discord.Client(intents=intents)
tree = app_commands.CommandTree(bot)

# Diccionario para almacenar eventos
events = {}

class EventCancelModal(Modal, title="Close Event"):
    def __init__(self, event_id):
        super().__init__()
        self.event_id = event_id
        self.reason = TextInput(
            label="Close reason",
            placeholder="Enter the reason for cancellation...",
            style=discord.TextStyle.paragraph,
            required=True,
            max_length=100
        )
        self.add_item(self.reason)

    async def on_submit(self, interaction: discord.Interaction):
        event = events.get(self.event_id)
        if event:
            # Crear un nuevo embed con el estado actualizado
            embed = event["message"].embeds[0]
            new_embed = discord.Embed.from_dict(embed.to_dict())
            
            # Buscar y actualizar el campo de estado
            for i, field in enumerate(new_embed.fields):
                if field.name == "Status":
                    new_embed.set_field_at(
                        i, 
                        name="Status", 
                        value=f"Cancelled, {self.reason.value}", 
                        inline=True
                    )
                    break
            
            await event["message"].edit(embed=new_embed, view=None)
            events[self.event_id]["status"] = "Cancelled"
            
            await interaction.response.send_message(
                "Event cancelled successfully!", 
                ephemeral=True
            )

class EndEventView(View):
    def __init__(self, event_id, event_type):
        super().__init__(timeout=None)
        self.event_id = event_id
        self.event_type = event_type

    async def interaction_check(self, interaction: discord.Interaction):
        # Verificar si el usuario tiene el rol requerido
        role = interaction.guild.get_role(REQUIRED_ROLE_ID)
        if role not in interaction.user.roles:
            await interaction.response.send_message(
                "Missing permissions", 
                ephemeral=True
            )
            return False
        return True

    @discord.ui.button(label="End Event", style=discord.ButtonStyle.secondary)
    async def simple_end(self, interaction: discord.Interaction, button: Button):
        await self.update_event_status(interaction, "Event Ended")

    @discord.ui.button(label="Event Won", style=discord.ButtonStyle.success)
    async def event_won(self, interaction: discord.Interaction, button: Button):
        await self.update_event_status(interaction, f"Event Ended | {self.event_type} won!")

    @discord.ui.button(label="Event Failed", style=discord.ButtonStyle.danger)
    async def event_failed(self, interaction: discord.Interaction, button: Button):
        await self.update_event_status(interaction, f"Event Ended | {self.event_type} failed!")

    async def update_event_status(self, interaction, status):
        event = events.get(self.event_id)
        if event:
            # Crear un nuevo embed con el estado actualizado
            embed = event["message"].embeds[0]
            new_embed = discord.Embed.from_dict(embed.to_dict())
            
            # Buscar y actualizar el campo de estado
            for i, field in enumerate(new_embed.fields):
                if field.name == "Status":
                    new_embed.set_field_at(
                        i, 
                        name="Status", 
                        value=status, 
                        inline=True
                    )
                    break
            
            await event["message"].edit(embed=new_embed, view=None)
            events[self.event_id]["status"] = status
            
            await interaction.response.edit_message(
                content=f"Event status updated to: {status}", 
                view=None
            )

class EventManageView(View):
    def __init__(self, event_id, event_type):
        super().__init__(timeout=None)
        self.event_id = event_id
        self.event_type = event_type

    async def interaction_check(self, interaction: discord.Interaction):
        # Verificar si el usuario tiene el rol requerido
        role = interaction.guild.get_role(REQUIRED_ROLE_ID)
        if role not in interaction.user.roles:
            await interaction.response.send_message(
                "Missing permissions", 
                ephemeral=True
            )
            return False
        return True

    @discord.ui.button(label="Cancel Event", style=discord.ButtonStyle.danger)
    async def cancel_event(self, interaction: discord.Interaction, button: Button):
        modal = EventCancelModal(self.event_id)
        await interaction.response.send_modal(modal)

    @discord.ui.button(label="Start Event", style=discord.ButtonStyle.success)
    async def start_event(self, interaction: discord.Interaction, button: Button):
        event = events.get(self.event_id)
        if event:
            # Crear un nuevo embed con el estado actualizado
            embed = event["message"].embeds[0]
            new_embed = discord.Embed.from_dict(embed.to_dict())
            
            # Buscar y actualizar el campo de estado
            for i, field in enumerate(new_embed.fields):
                if field.name == "Status":
                    new_embed.set_field_at(
                        i, 
                        name="Status", 
                        value="Ongoing Event", 
                        inline=True
                    )
                    break
            
            await event["message"].edit(embed=new_embed)
            events[self.event_id]["status"] = "Ongoing"
            
            await interaction.response.send_message(
                "Event started successfully!", 
                ephemeral=True
            )

    @discord.ui.button(label="End Event", style=discord.ButtonStyle.primary)
    async def end_event(self, interaction: discord.Interaction, button: Button):
        # Crear vista para opciones de fin de evento
        end_view = EndEventView(self.event_id, self.event_type)
        await interaction.response.send_message(
            "How did the event end?", 
            view=end_view, 
            ephemeral=True
        )

class EventButton(View):
    def __init__(self, event_id, event_type):
        super().__init__(timeout=None)
        self.event_id = event_id
        self.event_type = event_type

    @discord.ui.button(emoji="⚙️", style=discord.ButtonStyle.grey, custom_id="manage_event")
    async def manage_event(self, interaction: discord.Interaction, button: Button):
        # Verificar si el usuario tiene el rol requerido
        role = interaction.guild.get_role(REQUIRED_ROLE_ID)
        if role not in interaction.user.roles:
            await interaction.response.send_message(
                "Missing permissions", 
                ephemeral=True
            )
            return
        
        # Mostrar opciones de gestión
        manage_view = EventManageView(self.event_id, self.event_type)
        await interaction.response.send_message(
            "Manage Event Options:", 
            view=manage_view, 
            ephemeral=True
        )

@tree.command(
    name="schedule-event", 
    description="Schedule a new event", 
    guild=discord.Object(id=GUILD_ID)
)
@app_commands.describe(
    channel="Channel to send the event message",
    event_type="Type of event",
    host="Host of the event",
    time="Time of the event in Discord timestamp format (e.g., <t:1620000000:R>)",
    duration="Duration of the event",
    place="Place where the event will happen"
)
@app_commands.choices(event_type=[
    app_commands.Choice(name="Test1", value="Test1"),
    app_commands.Choice(name="Test2", value="Test2")
])
async def schedule_event(
    interaction: discord.Interaction, 
    channel: discord.TextChannel,
    event_type: app_commands.Choice[str],
    host: discord.Member,
    time: str,
    duration: str,
    place: str
):
    # Verificar si el usuario tiene el rol requerido
    role = interaction.guild.get_role(REQUIRED_ROLE_ID)
    if role not in interaction.user.roles:
        await interaction.response.send_message(
            "Missing permissions", 
            ephemeral=True
        )
        return

    # Generar ID único para el evento
    event_id = random.randint(10000, 99999)
    while event_id in events:
        event_id = random.randint(10000, 99999)

    # Crear embed para el evento
    embed = discord.Embed(
        title=f"Event: {event_type.name}",
        color=discord.Color.blue(),
        timestamp=datetime.now()
    )
    embed.add_field(name="Host", value=host.mention, inline=True)
    embed.add_field(name="Time", value=time, inline=True)
    embed.add_field(name="Duration", value=duration, inline=True)
    embed.add_field(name="Place", value=place, inline=False)
    embed.add_field(name="Event Type", value=event_type.name, inline=True)
    embed.add_field(name="Status", value="Scheduled", inline=True)
    embed.set_footer(text=f"Created by {interaction.user.display_name}, EventID: {event_id}")

    # Crear botón de gestión
    view = EventButton(event_id, event_type.name)

    # Enviar mensaje al canal especificado
    message = await channel.send(embed=embed, view=view)

    # Guardar información del evento
    events[event_id] = {
        "message": message,
        "channel": channel.id,
        "host": host.id,
        "type": event_type.name,
        "status": "Scheduled",
        "creator": interaction.user.id
    }

    await interaction.response.send_message(
        f"Event scheduled successfully! EventID: {event_id}", 
        ephemeral=True
    )

@bot.event
async def on_ready():
    await tree.sync(guild=discord.Object(id=GUILD_ID))

# Obtener el token de la variable de entorno
token = os.getenv('DISCORD_TOKEN')
if token is None:
    print("Error: La variable de entorno DISCORD_TOKEN no está configurada")
    exit(1)

# Ejecutar el bot
try:
    bot.run(token)
except Exception as e:
    print(f"Error al ejecutar el bot: {e}")
