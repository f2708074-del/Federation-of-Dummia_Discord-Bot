import discord
from discord import app_commands
from discord.ext import commands
import datetime

class PingCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(name="ping", description="Comprueba la latencia del bot")
    async def ping(self, interaction: discord.Interaction):
        # Calcular latencias
        bot_latency = round(self.bot.latency * 1000)  # Latencia de WebSocket
        start_time = datetime.datetime.now()
        
        # Enviar mensaje inicial y medir tiempo de respuesta
        await interaction.response.send_message("Calculando ping...")
        end_time = datetime.datetime.now()
        
        # Calcular latencia de ida y vuelta
        api_latency = round((end_time - start_time).total_seconds() * 1000)
        
        # Crear embed con la información
        embed = discord.Embed(
            title="🏓 Pong!",
            color=discord.Color.green(),
            timestamp=datetime.datetime.now()
        )
        embed.add_field(name="🤖 Latencia del Bot", value=f"{bot_latency}ms", inline=True)
        embed.add_field(name="📡 Latencia de la API", value=f"{api_latency}ms", inline=True)
        embed.set_footer(text=f"Solicitado por {interaction.user.name}")

        # Editar el mensaje original con la información completa
        await interaction.edit_original_response(content=None, embed=embed)

async def setup(bot):
    await bot.add_cog(PingCog(bot))
