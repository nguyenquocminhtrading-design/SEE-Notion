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
        self.tree.on_error = self.on_tree_error
        self.container = container
        self.flow: CommandFlow = container.flow

    async def on_tree_error(
        self, interaction: discord.Interaction, error: app_commands.AppCommandError
    ) -> None:
        if isinstance(error, app_commands.CommandNotFound):
            msg = "⚠️ Lệnh này chưa được đồng bộ trên Bot Server. Vui lòng báo Admin chạy `git pull` & restart bot server."
            try:
                if not interaction.response.is_done():
                    await interaction.response.send_message(msg, ephemeral=True)
                else:
                    await interaction.followup.send(msg, ephemeral=True)
            except Exception:
                pass
            return
        log.error("Unhandled command error: %s", error, exc_info=error)

    async def setup_hook(self) -> None:
        guild_id = get_settings().discord_guild_id
        if guild_id:
            try:
                guild = discord.Object(id=int(guild_id))
                self.tree.copy_global_to(guild=guild)
                await self.tree.sync(guild=guild)
                log.info("Đã sync slash commands cho Guild ID %s", guild_id)
            except Exception as e:
                log.warning("Không sync được Guild slash commands: %s", e)
        # Đồng bộ cả Global để phòng trường hợp gọi ngoài Guild hoặc dùng DM
        await self.tree.sync()
        log.info("Đã sync slash commands Global")

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


class BulkCompleteView(discord.ui.View):
    def __init__(self, bot, actor, tasks: list, requester_id: int):
        super().__init__(timeout=600)
        self.bot = bot
        self.actor = actor
        self.requester_id = requester_id
        self.tasks_map = {t["page_id"]: t for t in tasks}
        
        options = []
        for t in tasks[:25]:
            label = t["title"][:100]
            options.append(
                discord.SelectOption(
                    label=label, 
                    value=t["page_id"], 
                    description=f"{t.get('task_id')} | {t.get('deadline')}"[:100]
                )
            )
            
        self.select = discord.ui.Select(
            placeholder="Tick để chọn nhiều task...", 
            min_values=1, 
            max_values=len(options), 
            options=options
        )
        self.add_item(self.select)
        
        confirm_btn = discord.ui.Button(label="✅ Xác nhận", style=discord.ButtonStyle.success, row=1)
        confirm_btn.callback = self.confirm
        self.add_item(confirm_btn)
        
        cancel_btn = discord.ui.Button(label="❌ Hủy", style=discord.ButtonStyle.secondary, row=1)
        cancel_btn.callback = self.cancel
        self.add_item(cancel_btn)

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id != self.requester_id:
            await interaction.response.send_message("Chỉ người gọi lệnh mới dùng được.", ephemeral=True)
            return False
        return True

    async def confirm(self, interaction: discord.Interaction):
        if not self.select.values:
            await interaction.response.send_message("Bạn chưa chọn task nào!", ephemeral=True)
            return
            
        await interaction.response.defer()
        session = _new_session()
        try:
            selected_tasks = [self.tasks_map[pid] for pid in self.select.values]
            payload = {
                "intent": "bulk_complete",
                "tasks": selected_tasks,
            }
            result = await self.bot.flow.execute(actor=self.actor, payload=payload, session=session)
            await interaction.edit_original_response(content=result, view=None)
        except Exception as e:
            log.exception("Bulk complete fail")
            await interaction.edit_original_response(content=f"❌ Đã có lỗi khi thực thi: {e}", view=None)
        finally:
            session.close()
        self.stop()

    async def cancel(self, interaction: discord.Interaction):
        await interaction.response.edit_message(content="🚫 Đã hủy — không có gì thay đổi.", view=None)
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

    @bot.tree.command(name="complete", description="Hoàn thành task (Bỏ trống để chọn nhiều task)")
    @app_commands.describe(text="Mã task hoặc tên task (Bỏ trống để chọn từ danh sách)")
    async def complete(interaction: discord.Interaction, text: str | None = None):
        session = _new_session()
        try:
            await interaction.response.defer(thinking=True)
            actor = get_actor_by_discord_id(session, interaction.user.id)
            today = datetime.now(get_settings().business_tz).date()

            if text and text.strip():
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
            else:
                if not actor.user.notion_user_id:
                    await interaction.followup.send("❌ Tài khoản của bạn chưa link Notion user ID.")
                    return
                
                pages = await bot.flow.tasks.gateway.query_open_tasks()
                mine = [
                    bot.flow.tasks.gateway.parse_task(p)
                    for p in pages
                    if actor.user.notion_user_id in (bot.flow.tasks.gateway.parse_task(p).get("assignee_ids") or [])
                ]
                
                if not mine:
                    await interaction.followup.send("🎉 Bạn không có task nào đang mở để hoàn thành!")
                    return
                    
                view = BulkCompleteView(bot, actor, mine, interaction.user.id)
                await interaction.followup.send("📋 **Bạn muốn hoàn thành (các) task nào?** (có thể tick chọn nhiều task)", view=view)
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
        text="Nội dung template (dán trực tiếp text văn bản)",
        file="File đính kèm (.txt, .csv, .md chứa nội dung họp/task)",
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
        text: str | None = None,
        file: discord.Attachment | None = None,
        format: Literal["meeting", "csv"] | None = None,
    ):
        session = _new_session()
        try:
            await interaction.response.defer(thinking=True)
            if file:
                raw_bytes = await file.read()
                filename = file.filename.lower()
                if filename.endswith(".docx"):
                    from app.services.template_parser import extract_text_from_docx
                    text = extract_text_from_docx(raw_bytes)
                else:
                    text = raw_bytes.decode("utf-8", errors="replace")

            if not text or not text.strip():
                await interaction.followup.send("❌ Vui lòng nhập `text` (nội dung hoặc URL) hoặc đính kèm `file` template.")
                return

            text_clean = text.strip()
            import os
            from pathlib import Path

            if text_clean.startswith(("http://", "https://")):
                import httpx

                try:
                    async with httpx.AsyncClient(follow_redirects=True, timeout=15.0) as client:
                        resp = await client.get(text_clean)
                        if resp.status_code == 200:
                            if text_clean.lower().endswith(".docx") or resp.headers.get("Content-Type") == "application/vnd.openxmlformats-officedocument.wordprocessingml.document":
                                from app.services.template_parser import extract_text_from_docx
                                text = extract_text_from_docx(resp.content)
                            else:
                                text = resp.text
                        else:
                            await interaction.followup.send(
                                f"❌ Không thể tải nội dung từ URL (mã lỗi HTTP {resp.status_code})."
                            )
                            return
                except Exception as ex:
                    await interaction.followup.send(f"❌ Lỗi khi tải nội dung từ URL: {ex}")
                    return
            elif os.path.exists(text_clean) and os.path.isfile(text_clean):
                try:
                    if text_clean.lower().endswith(".docx"):
                        from app.services.template_parser import extract_text_from_docx
                        with open(text_clean, "rb") as f:
                            text = extract_text_from_docx(f.read())
                    else:
                        text = Path(text_clean).read_text(encoding="utf-8", errors="replace")
                except Exception as ex:
                    await interaction.followup.send(f"❌ Lỗi khi đọc file local: {ex}")
                    return

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
                    assignee_str = (
                        ", ".join(task_data["assignee_names_raw"])
                        if task_data.get("assignee_names_raw")
                        else "Chưa gán"
                    )
                    due_str = task_data.get("deadline") or "Chưa có"
                    status_str = f" | {task_data['status']}" if task_data.get("status") else ""
                    all_summaries.append(
                        f"• **{i + 1}. {task_data['title']}** (👤 {assignee_str} | 📅 {due_str}{status_str})"
                    )
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

            # Create combined preview with character limit safety (< 1900 chars)
            body_lines = [f"📋 **Xác nhận tạo {len(all_payloads)} task:**\n"]
            included_count = 0

            for line in all_summaries:
                current_text = "\n".join(body_lines) + "\n" + line
                if len(current_text) > 1500:
                    break
                body_lines.append(line)
                included_count += 1

            if included_count < len(all_summaries):
                body_lines.append(f"\n... và {len(all_summaries) - included_count} task nữa.")

            if all_warnings:
                body_lines.append("\n⚠️ **Cảnh báo:**\n" + "\n".join(all_warnings[:5]))

            body_lines.append("\n_Hết hạn sau 10 phút._")
            body = "\n".join(body_lines)

            if len(body) > 1900:
                body = body[:1850] + "\n...\n_Hết hạn sau 10 phút._"

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
