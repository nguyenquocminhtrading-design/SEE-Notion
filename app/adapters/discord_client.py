"""Discord bot — lớp tiếp nhận MVP. Chỉ nhận lệnh + render; logic nằm ở services."""

import logging
from datetime import datetime
from typing import Literal

import discord
from discord import app_commands

from app.config import get_settings
from app.models.preview import ActionError
from app.services.authz import NotAuthorized, get_actor_by_discord_id
from app.services.command_flow import CommandFlow
from app.services.confirmation import NonceError
from app.services.parser import ParseError

log = logging.getLogger(__name__)


class SEENotionBot(discord.Client):
    def __init__(self, container):
        intents = discord.Intents.default()
        intents.message_content = False  # chỉ dùng slash command — không cần intent nhạy cảm
        super().__init__(intents=intents)
        self.tree = app_commands.CommandTree(self)
        self.container = container
        self.flow: CommandFlow = container.flow

    async def setup_hook(self) -> None:
        guild_id = get_settings().discord_guild_id
        guild = discord.Object(id=int(guild_id)) if guild_id else None
        if guild:
            self.tree.copy_global_to(guild=guild)
            await self.tree.sync(guild=guild)
        else:
            await self.tree.sync()
        log.info("Đã sync slash commands")

    async def on_ready(self) -> None:
        log.info("Bot online: %s", self.user)
        self.container.set_discord_sender(self.send_dm)

    async def send_dm(self, discord_id: str, text: str) -> None:
        """Kênh Discord DM cho reminder engine (best-effort)."""
        user = await self.fetch_user(int(discord_id))
        await user.send(text[:1900])


class ConfirmView(discord.ui.View):
    def __init__(self, bot: SEENotionBot, nonce: str, requester_id: int, expires_in: int):
        super().__init__(timeout=expires_in)
        self.bot = bot
        self.nonce = nonce
        self.requester_id = requester_id

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id != self.requester_id:
            await interaction.response.send_message(
                "Chỉ người tạo lệnh mới được xác nhận.", ephemeral=True
            )
            return False
        return True

    @discord.ui.button(label="✅ Xác nhận", style=discord.ButtonStyle.success)
    async def confirm(self, interaction: discord.Interaction, _button: discord.ui.Button):
        await interaction.response.defer()
        session = _new_session()
        try:
            payload = self.bot.container.confirmations.redeem(
                session, self.nonce, self.requester_id
            )
            actor = get_actor_by_discord_id(session, self.requester_id)
            result = await self.bot.flow.execute(actor=actor, payload=payload, session=session)
            await interaction.edit_original_response(content=result, view=None)
        except (NonceError, NotAuthorized, ActionError) as e:
            await interaction.edit_original_response(
                content=f"❌ {getattr(e, 'message', e)}", view=None
            )
        except Exception:
            log.exception("Execute fail")
            await interaction.edit_original_response(
                content="❌ Đã có lỗi khi thực thi. Đã ghi log — thử lại sau.", view=None
            )
        finally:
            session.close()
        self.stop()

    @discord.ui.button(label="❌ Hủy", style=discord.ButtonStyle.secondary)
    async def cancel(self, interaction: discord.Interaction, _button: discord.ui.Button):
        await interaction.response.edit_message(
            content="🚫 Đã hủy — không có gì thay đổi.", view=None
        )
        self.stop()


def _new_session():
    from app.db.session import get_session

    return get_session()


def setup_commands(bot: SEENotionBot) -> None:
    @bot.tree.command(name="create", description="Tạo task mới")
    @app_commands.describe(
        name="Tên task",
        assignees="Người thực hiện (nhập tên, cách nhau bằng dấu phẩy: Minh, Cường, Hân)",
        due_date="Hạn chót (VD: 30/09/2026 hoặc 'thứ 6')",
        priority="Độ ưu tiên",
        task_type="Loại công việc",
        effort="Độ khó",
        start_date="Ngày bắt đầu (tùy chọn)",
        description="Mô tả thêm (tùy chọn)",
    )
    async def create(
        interaction: discord.Interaction,
        name: str,
        assignees: str,
        due_date: str,
        priority: Literal["High", "Medium", "Low"],
        task_type: Literal["Sự kiện", "Họp", "Báo cáo"],
        effort: Literal["High", "Medium", "Low"],
        start_date: str | None = None,
        description: str | None = None,
    ):
        session = _new_session()
        try:
            await interaction.response.defer(thinking=True)
            actor = get_actor_by_discord_id(session, interaction.user.id)
            today = datetime.now(get_settings().business_tz).date()

            fields = {
                "title": name,
                "assignee_name_raw": assignees,
                "deadline": due_date,
                "priority": priority,
                "task_type": task_type,
                "effort": effort,
                "start_date": start_date,
                "description": description,
            }

            prep = await bot.flow.prepare_create(
                actor=actor, fields=fields, today=today, session=session
            )

            nonce = bot.container.confirmations.create(
                session,
                discord_user=str(interaction.user.id),
                channel_id=str(interaction.channel_id),
                payload=prep["payload"],
                summary_lines=prep["summary_lines"],
                warnings=prep["warnings"],
            )
            body = "📋 **Xác nhận tạo task:**\n" + "\n".join(prep["summary_lines"])
            if prep["warnings"]:
                body += "\n⚠️ " + "\n⚠️ ".join(prep["warnings"])
            body += f"\n\n_Hết hạn sau {prep['expires_in_seconds'] // 60} phút._"
            await interaction.followup.send(
                body, view=ConfirmView(bot, nonce, interaction.user.id, prep["expires_in_seconds"])
            )
        except (ParseError, ActionError) as e:
            msg = f"❓ {e.message}" if isinstance(e, ActionError) else f"❓ {e}"
            options = getattr(e, "options", [])
            if options:
                msg += "\nÝ bạn là: " + " / ".join(options)
            await interaction.followup.send(msg[:1900])
        except NotAuthorized as e:
            await interaction.followup.send(f"🔒 {e}")
        except Exception:
            log.exception("Command fail")
            await interaction.followup.send("❌ Đã có lỗi bất ngờ. Đã ghi log — thử lại sau.")
        finally:
            session.close()

    @bot.tree.command(name="update", description="Cập nhật task (VD: Dời TSK-001 sang 10/10)")
    @app_commands.describe(text="Lệnh cập nhật")
    async def update(interaction: discord.Interaction, text: str):
        session = _new_session()
        try:
            await interaction.response.defer(thinking=True)
            actor = get_actor_by_discord_id(session, interaction.user.id)
            today = datetime.now(get_settings().business_tz).date()

            prep = await bot.flow.prepare_update(
                actor=actor, text=text, today=today, session=session
            )

            nonce = bot.container.confirmations.create(
                session,
                discord_user=str(interaction.user.id),
                channel_id=str(interaction.channel_id),
                payload=prep["payload"],
                summary_lines=prep["summary_lines"],
                warnings=prep["warnings"],
            )
            body = "📋 **Xác nhận cập nhật:**\n" + "\n".join(prep["summary_lines"])
            if prep["warnings"]:
                body += "\n⚠️ " + "\n⚠️ ".join(prep["warnings"])
            body += f"\n\n_Hết hạn sau {prep['expires_in_seconds'] // 60} phút._"
            await interaction.followup.send(
                body, view=ConfirmView(bot, nonce, interaction.user.id, prep["expires_in_seconds"])
            )
        except (ParseError, ActionError) as e:
            msg = f"❓ {e.message}" if isinstance(e, ActionError) else f"❓ {e}"
            options = getattr(e, "options", [])
            if options:
                msg += "\nÝ bạn là: " + " / ".join(options)
            await interaction.followup.send(msg[:1900])
        except NotAuthorized as e:
            await interaction.followup.send(f"🔒 {e}")
        except Exception:
            log.exception("Command fail")
            await interaction.followup.send("❌ Đã có lỗi bất ngờ. Đã ghi log — thử lại sau.")
        finally:
            session.close()

    @bot.tree.command(name="complete", description="Hoàn thành task (VD: xong TSK-001)")
    @app_commands.describe(text="Mã task hoặc tên task")
    async def complete(interaction: discord.Interaction, text: str):
        session = _new_session()
        try:
            await interaction.response.defer(thinking=True)
            actor = get_actor_by_discord_id(session, interaction.user.id)
            today = datetime.now(get_settings().business_tz).date()

            prep = await bot.flow.prepare_complete(
                actor=actor, text=text, today=today, session=session
            )

            nonce = bot.container.confirmations.create(
                session,
                discord_user=str(interaction.user.id),
                channel_id=str(interaction.channel_id),
                payload=prep["payload"],
                summary_lines=prep["summary_lines"],
                warnings=prep["warnings"],
            )
            body = "📋 **Xác nhận hoàn thành:**\n" + "\n".join(prep["summary_lines"])
            if prep["warnings"]:
                body += "\n⚠️ " + "\n⚠️ ".join(prep["warnings"])
            body += f"\n\n_Hết hạn sau {prep['expires_in_seconds'] // 60} phút._"
            await interaction.followup.send(
                body, view=ConfirmView(bot, nonce, interaction.user.id, prep["expires_in_seconds"])
            )
        except (ParseError, ActionError) as e:
            msg = f"❓ {e.message}" if isinstance(e, ActionError) else f"❓ {e}"
            options = getattr(e, "options", [])
            if options:
                msg += "\nÝ bạn là: " + " / ".join(options)
            await interaction.followup.send(msg[:1900])
        except NotAuthorized as e:
            await interaction.followup.send(f"🔒 {e}")
        except Exception:
            log.exception("Command fail")
            await interaction.followup.send("❌ Đã có lỗi bất ngờ. Đã ghi log — thử lại sau.")
        finally:
            session.close()

    @bot.tree.command(name="my", description="Task đang mở của bạn")
    async def my(interaction: discord.Interaction):
        session = _new_session()
        try:
            await interaction.response.defer(thinking=True)
            actor = get_actor_by_discord_id(session, interaction.user.id)
            parsed = _parse_list_my()
            prep = await bot.flow.handle_query(parsed, actor=actor, session=session)
            await interaction.followup.send(prep["query_result"][:1900])
        except (ActionError, NotAuthorized) as e:
            await interaction.followup.send(f"ℹ️ {getattr(e, 'message', e)}")
        finally:
            session.close()

    @bot.tree.command(
        name="bulk-create", description="Tạo nhiều task từ template (meeting minutes/CSV)"
    )
    @app_commands.describe(
        text="Nội dung template (Action Items Tracker hoặc CSV)",
        format="Định dạng: 'meeting' cho meeting minutes, 'csv' cho CSV",
    )
    @app_commands.choices(
        format=[
            app_commands.Choice(name="Meeting Minutes", value="meeting"),
            app_commands.Choice(name="CSV", value="csv"),
        ]
    )
    async def bulk_create(
        interaction: discord.Interaction,
        text: str,
        format: Literal["meeting", "csv"] | None = None,
    ):
        session = _new_session()
        try:
            await interaction.response.defer(thinking=True)
            actor = get_actor_by_discord_id(session, interaction.user.id)
            today = datetime.now(get_settings().business_tz).date()

            # Parse template
            from app.services.template_parser import TemplateParseError, parse_template_input

            try:
                tasks_data = parse_template_input(text, format)
            except TemplateParseError as e:
                await interaction.followup.send(
                    f"❌ Lỗi parse template dòng {e.line_num}: {e.message}"
                )
                return

            if not tasks_data:
                await interaction.followup.send("❌ Không tìm thấy task nào trong template.")
                return

            # Prepare all tasks
            all_summaries = []
            all_warnings = []
            all_payloads = []

            for i, task_data in enumerate(tasks_data):
                # Validate each task
                if not task_data.get("title"):
                    all_warnings.append(f"Dòng {task_data.get('line_num', i + 1)}: Thiếu tên task")
                    continue
                if not task_data.get("deadline"):
                    all_warnings.append(
                        f"Dòng {task_data.get('line_num', i + 1)} ({task_data['title']}): Thiếu deadline"
                    )
                    continue

                # Parse deadline
                deadline = task_data["deadline"]
                if isinstance(deadline, str):
                    from app.services.validator import try_parse_date_simple

                    parsed_due = try_parse_date_simple(deadline, today)
                    if not parsed_due:
                        parsed_due = await bot.flow.parser.parse_date(deadline, today.isoformat())
                    task_data["deadline"] = parsed_due or deadline

                # Build fields for prepare_create
                fields = {
                    "title": task_data["title"],
                    "assignee_name_raw": ", ".join(task_data["assignee_names_raw"])
                    if task_data["assignee_names_raw"]
                    else "",
                    "deadline": task_data["deadline"],
                    "priority": task_data["priority"],
                    "task_type": task_data.get("task_type", ""),
                    "effort": task_data.get("effort", ""),
                    "start_date": task_data.get("start_date", ""),
                    "description": task_data.get("description", ""),
                }

                try:
                    prep = await bot.flow.prepare_create(
                        actor=actor, fields=fields, today=today, session=session
                    )
                    all_payloads.append(prep["payload"])
                    all_summaries.append(f"**{i + 1}. {task_data['title']}**")
                    all_summaries.extend([f"   {line}" for line in prep["summary_lines"]])
                    if prep["warnings"]:
                        all_warnings.extend(
                            [
                                f"Dòng {task_data.get('line_num', i + 1)}: {w}"
                                for w in prep["warnings"]
                            ]
                        )
                except (ParseError, ActionError) as e:
                    all_warnings.append(
                        f"Dòng {task_data.get('line_num', i + 1)} ({task_data['title']}): {e.message}"
                    )

            if not all_payloads:
                await interaction.followup.send("❌ Không có task hợp lệ nào để tạo.")
                return

            # Create combined preview
            body = f"📋 **Xác nhận tạo {len(all_payloads)} task:**\n\n"
            body += "\n".join(all_summaries[:20])  # Limit preview length
            if len(all_summaries) > 20:
                body += f"\n... và {len(all_summaries) - 20} task nữa"

            if all_warnings:
                body += "\n\n⚠️ **Cảnh báo:**\n" + "\n".join(all_warnings[:10])

            body += "\n\n_Hết hạn sau 10 phút._"

            # Store all payloads in confirmation

            combined_payload = {
                "intent": "bulk_create",
                "tasks": all_payloads,
                "actor": actor.display_name,
            }

            nonce = bot.container.confirmations.create(
                session,
                discord_user=str(interaction.user.id),
                channel_id=str(interaction.channel_id),
                payload=combined_payload,
                summary_lines=[f"Tạo {len(all_payloads)} task từ template"],
                warnings=all_warnings,
            )

            await interaction.followup.send(
                body, view=ConfirmView(bot, nonce, interaction.user.id, 600)
            )

        except NotAuthorized as e:
            await interaction.followup.send(f"🔒 {e}")
        except Exception:
            log.exception("Bulk create fail")
            await interaction.followup.send("❌ Đã có lỗi bất ngờ. Đã ghi log — thử lại sau.")
        finally:
            session.close()


def _parse_list_my():
    from app.models.parsed_command import ParsedCommand

    return ParsedCommand(intent="list_my_tasks", confidence=1.0)


def run_bot(container) -> SEENotionBot:
    bot = SEENotionBot(container)
    setup_commands(bot)
    return bot
