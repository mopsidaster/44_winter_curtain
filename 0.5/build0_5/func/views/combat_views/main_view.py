# -*- coding: utf-8 -*-
# func/views/combat_views/main_view.py - Главное меню боя (0.4.8.7.5)
#
# ИСТОРИЯ:
#   0.4.4.7 — вынесено
#   0.4.4.7.3 — ИСПРАВЛЕНИЕ: MG стрелял 4 раза
#   0.4.4.8 — safe_defer
#   0.4.5 — defer + edit_original_response
#   0.4.6 — групповой бой
#   0.4.6.2 — view для текущего актора
#   0.4.7.2 — ФИКС очереди
#   0.4.8.7 — Кнопка «💥 Дуплет» (только Дуплет)
#   0.4.8.7.5 — цветовые эмодзи дистанции (Близко=🔴, Средняя=🟡, Далеко=🟢)

import discord
import uuid

from ..helpers import combat_manager, handle_combat_action
from ...weapon_system import (
    is_spec_weapon,
    is_smg,
    is_mg,
    is_heavy_mg,
    get_current_ammo,
    get_shots_per_action,
    get_weapon_type,
    get_weapon_double_shot_config,
)
from config.map_config import WEAPONS
from utils.discord_helpers import safe_defer
from utils.logger import get_logger

logger = get_logger()

# 0.4.8.7.5: цвет дистанции
DISTANCE_LABELS = {
    "close": "🔴 Близко",   # опасно
    "medium": "🟡 Средняя", # средне
    "far": "🟢 Далеко",     # безопасно
}

MAX_SHOTS_BY_TYPE = {
    "mg": 3,
    "smg": 4,
    "assault": 2,
}


def _get_safe_shots_count(weapon_id: str) -> int:
    weapon_type = get_weapon_type(weapon_id)
    shots = get_shots_per_action(weapon_id)
    max_by_type = MAX_SHOTS_BY_TYPE.get(weapon_type)
    if max_by_type is not None:
        shots = min(shots, max_by_type)
    return max(1, shots)


class CombatView(discord.ui.View):
    def __init__(self, user_id: int):
        super().__init__(timeout=300)
        self.user_id = user_id
        self.menu_id = uuid.uuid4().hex[:8]
        self.action_type = None
        self._add_buttons()

    def _has_throwables(self, combat) -> bool:
        return (
                combat.player.get_grenades_total() > 0
                or combat.player.get_knives_total() > 0
        )

    def _find_player_in_combat(self, combat, user_id: int):
        for p in combat.get_all_players():
            if p.user_id == user_id:
                return p
        return None

    def _add_buttons(self):
        combat = combat_manager.get_combat(self.user_id)
        if not combat or not combat.is_active:
            return

        my_player = self._find_player_in_combat(combat, self.user_id)

        if my_player is None:
            not_member_btn = discord.ui.Button(
                label="❌ Вы не участник боя",
                style=discord.ButtonStyle.secondary,
                disabled=True,
                custom_id=f"cb_notmember_{self.menu_id}",
            )
            self.add_item(not_member_btn)
            return

        if not my_player.is_alive:
            dead_btn = discord.ui.Button(
                label="💀 Вы мертвы",
                style=discord.ButtonStyle.danger,
                disabled=True,
                custom_id=f"cb_dead_{self.menu_id}",
            )
            self.add_item(dead_btn)
            return

        is_my_turn = True
        if hasattr(combat, 'is_current_actor'):
            is_my_turn = combat.is_current_actor(self.user_id)

        if not is_my_turn:
            try:
                current = combat.get_current_actor()
                current_name = current.name
            except Exception:
                current_name = "союзник"
            wait_btn = discord.ui.Button(
                label=f"⏳ Ходит {current_name}",
                style=discord.ButtonStyle.secondary,
                disabled=True,
                custom_id=f"cb_wait_{self.menu_id}",
            )
            self.add_item(wait_btn)
            return

        actor = combat.get_current_actor() if hasattr(combat, 'get_current_actor') else combat.player

        is_spec = is_spec_weapon(actor.weapon)
        smg = is_smg(actor.weapon)
        mg = is_mg(actor.weapon)
        heavy_mg = is_heavy_mg(actor.weapon)

        can_shoot_now = combat.can_shoot_now()

        can_finish = combat.enemy.can_finish() if combat.enemy else False
        can_spare = combat.enemy.can_be_spared() if combat.enemy else False

        if is_spec:
            has_ammo = actor.get_shell_ammo_count() > 0
        else:
            has_ammo = get_current_ammo(actor.weapon, actor) > 0

        if can_finish:
            finish_button = discord.ui.Button(
                label="⚔️ Добить",
                style=discord.ButtonStyle.danger,
                row=0,
                custom_id=f"cb_finish_{self.menu_id}"
            )
            finish_button.callback = self.finish_callback
            self.add_item(finish_button)

        if can_spare:
            spare_button = discord.ui.Button(
                label="🕊️ Пощадить",
                style=discord.ButtonStyle.success,
                row=0,
                custom_id=f"cb_spare_{self.menu_id}"
            )
            spare_button.callback = self.spare_callback
            self.add_item(spare_button)

        if is_spec:
            single_btn = discord.ui.Button(
                label="💥 Прицельный",
                style=discord.ButtonStyle.danger,
                row=0,
                custom_id=f"cb_gr_single_{self.menu_id}",
                disabled=not has_ammo or combat.distance == "close"
            )
            single_btn.callback = self.grenade_single_callback
            self.add_item(single_btn)

            group_btn = discord.ui.Button(
                label="💣 По группе",
                style=discord.ButtonStyle.danger,
                row=0,
                custom_id=f"cb_gr_group_{self.menu_id}",
                disabled=not has_ammo
            )
            group_btn.callback = self.grenade_group_callback
            self.add_item(group_btn)
        else:
            shoot_label = "🔫 Выстрел"
            if mg:
                shoot_label = "🔫 Очередь (3)"
            elif smg:
                shoot_label = "🔫 Очередь (4)"

            shoot_btn = discord.ui.Button(
                label=shoot_label,
                style=discord.ButtonStyle.danger,
                row=0,
                custom_id=f"cb_shoot_{self.menu_id}",
                disabled=(not has_ammo) or (not can_shoot_now)
            )
            shoot_btn.callback = self.shoot_callback
            self.add_item(shoot_btn)

            # 0.4.8.7: Дуплет
            double_cfg = get_weapon_double_shot_config(actor.weapon)
            if double_cfg:
                ammo_needed = int(double_cfg.get("ammo_cost", 2))
                if actor.get_shell_ammo_count() >= ammo_needed:
                    double_btn = discord.ui.Button(
                        label="💥 Дуплет",
                        style=discord.ButtonStyle.danger,
                        row=0,
                        custom_id=f"cb_double_{self.menu_id}",
                        disabled=(combat.distance == "far") or (not can_shoot_now),
                    )
                    double_btn.callback = self.double_callback
                    self.add_item(double_btn)

        melee_button = discord.ui.Button(
            label="👊 Рукопашная",
            style=discord.ButtonStyle.success,
            row=0,
            custom_id=f"cb_melee_{self.menu_id}",
            disabled=(combat.distance != "close")
        )
        melee_button.callback = self.melee_callback
        self.add_item(melee_button)

        action_menu_btn = discord.ui.Button(
            label="⚙️ Действие",
            style=discord.ButtonStyle.primary,
            row=0,
            custom_id=f"cb_actions_{self.menu_id}"
        )
        action_menu_btn.callback = self.actions_callback
        self.add_item(action_menu_btn)

        for dist_id in ["close", "medium", "far"]:
            is_current = combat.distance == dist_id
            label = DISTANCE_LABELS.get(dist_id, dist_id)
            if is_current:
                label = f"📍 {label}"

            dist_button = discord.ui.Button(
                label=label,
                style=discord.ButtonStyle.success if is_current else discord.ButtonStyle.secondary,
                row=1,
                custom_id=f"cb_dist_{self.menu_id}_{dist_id}",
                disabled=is_current
            )
            dist_button.callback = self.create_distance_callback(dist_id)
            self.add_item(dist_button)

        if not is_spec:
            parts = ["голова", "торс", "руки", "ноги"]
            available_parts = combat.get_target_parts()
            part_emojis = {"голова": "🎯", "торс": "🫀", "руки": "💪", "ноги": "🦵"}

            for idx, part in enumerate(parts):
                is_available = part in available_parts
                style = discord.ButtonStyle.danger if part == "голова" else discord.ButtonStyle.secondary

                button = discord.ui.Button(
                    label=f"{part_emojis.get(part, '')} {part.capitalize()}",
                    style=style,
                    row=2,
                    custom_id=f"cb_part_{self.menu_id}_{idx}_{part}",
                    disabled=not is_available
                )
                button.callback = self.create_part_callback(part)
                self.add_item(button)

        alive_enemies = combat.get_alive_enemies()
        if len(combat.enemies) > 1:
            for idx, enemy_obj in enumerate(combat.enemies):
                if not enemy_obj.is_alive:
                    continue

                is_target = (idx == combat.target_index)
                label = f"{'🎯 ' if is_target else ''}{enemy_obj.emoji} {enemy_obj.display_name}"[:80]

                target_button = discord.ui.Button(
                    label=label,
                    style=discord.ButtonStyle.success if is_target else discord.ButtonStyle.secondary,
                    row=3,
                    custom_id=f"cb_target_{self.menu_id}_{idx}",
                    disabled=is_target
                )
                target_button.callback = self.create_target_callback(idx)
                self.add_item(target_button)

        if len(alive_enemies) <= 2:
            defend_button = discord.ui.Button(
                label="🛡️ Защита",
                style=discord.ButtonStyle.secondary,
                row=3,
                custom_id=f"cb_defend_{self.menu_id}"
            )
            defend_button.callback = self.defend_callback
            self.add_item(defend_button)

    async def _check_turn(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id != self.user_id:
            await interaction.response.send_message("❌ Не ваш бой!", ephemeral=True)
            return False

        combat = combat_manager.get_combat(self.user_id)
        if not combat or not combat.is_active:
            await interaction.response.send_message("❌ Бой завершён!", ephemeral=True)
            return False

        if hasattr(combat, 'is_current_actor') and not combat.is_current_actor(self.user_id):
            try:
                current = combat.get_current_actor()
                current_name = current.name
            except Exception:
                current_name = "союзник"
            await interaction.response.send_message(
                f"⏳ Сейчас ходит **{current_name}**.", ephemeral=True
            )
            return False

        if not combat.can_act():
            await interaction.response.send_message("⏳ Дождитесь хода врага!", ephemeral=True)
            return False

        return True

    def create_part_callback(self, part: str):
        async def callback(interaction: discord.Interaction):
            logger.info(f"🎯 part_callback: part={part}, action_type={self.action_type}")

            if not await self._check_turn(interaction):
                return

            combat = combat_manager.get_combat(self.user_id)
            if not combat:
                return

            if self.action_type is None:
                await interaction.response.send_message(
                    "❌ Сначала выберите действие!", ephemeral=True
                )
                return

            # 0.4.8.7: Дуплет
            if self.action_type == "shoot_double":
                if not await safe_defer(interaction):
                    return
                embed, view = await handle_combat_action(
                    interaction, "shoot_double", part
                )
                self.action_type = None
                if embed is None:
                    return
                try:
                    await interaction.edit_original_response(embed=embed, view=view)
                except Exception as e:
                    logger.error(f"Ошибка shoot_double: {e}")
                return

            if self.action_type == "shoot":
                actor = combat.get_current_actor()
                weapon_id = actor.weapon
                weapon_type = get_weapon_type(weapon_id)

                requested = _get_safe_shots_count(weapon_id)
                current_ammo = get_current_ammo(weapon_id, actor)

                if weapon_type in ('assault', 'smg', 'mg') and requested >= 2:
                    requested = min(requested, current_ammo)

                    logger.info(
                        f"🎯 [MULTISHOT] weapon={weapon_id}, type={weapon_type}, "
                        f"requested={requested}, ammo={current_ammo}"
                    )

                    if requested < 1:
                        await interaction.response.send_message("❌ Нет патронов!", ephemeral=True)
                        return

                    primary_idx = combat.target_index
                    primary_part = part

                    if requested == 1:
                        if not await safe_defer(interaction):
                            return
                        embed, view = await handle_combat_action(interaction, "shoot", part)
                        if embed is None:
                            return
                        try:
                            await interaction.edit_original_response(embed=embed, view=view)
                        except Exception as e:
                            logger.error(f"Ошибка shoot (single): {e}")
                        return

                    plan = [(primary_idx, primary_part)] * requested

                    logger.info(f"🎯 [MULTISHOT] plan_len={len(plan)}, shots={requested}")

                    if not await safe_defer(interaction):
                        return

                    embed = combat.get_status_embed()
                    embed.add_field(
                        name=f"🎯 Выстрел 1/{requested}",
                        value=f"Цель #{primary_idx + 1} — **{primary_part}**\n\n"
                              f"Куда направить **следующий** выстрел?",
                        inline=False
                    )

                    from .multishot import _MultiShotMenu
                    view = _MultiShotMenu(
                        self.user_id, self.menu_id,
                        combat=combat,
                        shots_count=requested,
                        plan=plan,
                    )
                    try:
                        await interaction.edit_original_response(embed=embed, view=view)
                    except Exception as e:
                        logger.error(f"Ошибка multishot menu: {e}")
                    return

            if not await safe_defer(interaction):
                return

            embed, view = await handle_combat_action(interaction, self.action_type, part)
            self.action_type = None

            if embed is None:
                return

            try:
                await interaction.edit_original_response(embed=embed, view=view)
            except discord.errors.NotFound:
                pass
            except Exception as e:
                logger.error(f"Ошибка edit (part): {e}")

        return callback

    def create_distance_callback(self, distance: str):
        async def callback(interaction: discord.Interaction):
            if not await self._check_turn(interaction):
                return

            if not await safe_defer(interaction):
                return

            embed, view = await handle_combat_action(interaction, "change_distance", distance)
            if embed is None:
                return

            try:
                await interaction.edit_original_response(embed=embed, view=view)
            except discord.errors.NotFound:
                pass
            except Exception as e:
                logger.error(f"Ошибка смены дистанции: {e}")

        return callback

    def create_target_callback(self, index: int):
        async def callback(interaction: discord.Interaction):
            if not await self._check_turn(interaction):
                return

            if not await safe_defer(interaction):
                return

            embed, view = await handle_combat_action(interaction, "change_target", str(index))
            if embed is None:
                return

            try:
                await interaction.edit_original_response(embed=embed, view=view)
            except discord.errors.NotFound:
                pass
            except Exception as e:
                logger.error(f"Ошибка смены цели: {e}")

        return callback

    async def shoot_callback(self, interaction: discord.Interaction):
        logger.info(f"🔫 shoot_callback: user={interaction.user.id}")

        if not await self._check_turn(interaction):
            return

        combat = combat_manager.get_combat(self.user_id)
        actor = combat.get_current_actor()

        if not combat.can_shoot_now():
            await interaction.response.send_message(
                "🔧 **Перезарядка Heavy MG (2/2)!** Можете только в рукопашную.",
                ephemeral=True
            )
            return
        if get_current_ammo(actor.weapon, actor) <= 0:
            await interaction.response.send_message("❌ Нет патронов!", ephemeral=True)
            return

        self.action_type = "shoot"

        if not await safe_defer(interaction):
            return

        embed = combat.get_status_embed()
        embed.add_field(name="🔫 Выберите часть тела", value="Нажмите на кнопку ниже:", inline=False)
        try:
            await interaction.edit_original_response(embed=embed, view=self)
        except Exception as e:
            logger.error(f"Ошибка shoot_callback: {e}")

    # 0.4.8.7: Дуплет
    async def double_callback(self, interaction: discord.Interaction):
        logger.info(f"💥 double_callback: user={interaction.user.id}")

        if not await self._check_turn(interaction):
            return

        combat = combat_manager.get_combat(self.user_id)
        actor = combat.get_current_actor()

        double_cfg = get_weapon_double_shot_config(actor.weapon)
        if not double_cfg:
            await interaction.response.send_message(
                "❌ У этого оружия нет дуплета!", ephemeral=True
            )
            return
        ammo_needed = int(double_cfg.get("ammo_cost", 2))
        if actor.get_shell_ammo_count() < ammo_needed:
            await interaction.response.send_message(
                f"❌ Для дуплета нужно {ammo_needed} патрона!", ephemeral=True
            )
            return
        if combat.distance == "far":
            await interaction.response.send_message(
                "❌ Дуплет не работает вдаль!", ephemeral=True
            )
            return

        self.action_type = "shoot_double"

        if not await safe_defer(interaction):
            return

        embed = combat.get_status_embed()
        embed.add_field(
            name="💥 Дуплет — выберите часть тела",
            value=(
                f"**{ammo_needed}** патрона, **×2** урон, "
                f"**−10%** точность. Картечь в упор = **×4**.\n"
                f"Нажмите на кнопку ниже:"
            ),
            inline=False
        )
        try:
            await interaction.edit_original_response(embed=embed, view=self)
        except Exception as e:
            logger.error(f"Ошибка double_callback: {e}")

    async def melee_callback(self, interaction: discord.Interaction):
        logger.info(f"👊 melee_callback: user={interaction.user.id}")

        if not await self._check_turn(interaction):
            return

        combat = combat_manager.get_combat(self.user_id)
        actor = combat.get_current_actor()

        if combat.distance != "close":
            await interaction.response.send_message(
                "❌ Рукопашная только на «Близко»! Смените дистанцию.",
                ephemeral=True
            )
            return
        if actor.is_body_part_destroyed("руки"):
            await interaction.response.send_message("❌ Руки уничтожены!", ephemeral=True)
            return

        self.action_type = "melee"

        if not await safe_defer(interaction):
            return

        embed = combat.get_status_embed()
        embed.add_field(name="👊 Выберите часть тела", value="Нажмите на кнопку ниже:", inline=False)
        try:
            await interaction.edit_original_response(embed=embed, view=self)
        except Exception as e:
            logger.error(f"Ошибка melee_callback: {e}")

    async def actions_callback(self, interaction: discord.Interaction):
        logger.info(f"⚙️ actions_callback: user={interaction.user.id}")

        if not await self._check_turn(interaction):
            return

        combat = combat_manager.get_combat(self.user_id)

        if not await safe_defer(interaction):
            return

        try:
            from .action_submenu import _ActionSubmenu
            view = _ActionSubmenu(combat.get_current_actor().user_id)
        except Exception as e:
            logger.error(f"⚙️ actions_callback: ОШИБКА создания _ActionSubmenu: {e}", exc_info=True)
            try:
                await interaction.followup.send(f"❌ Ошибка подменю: {e}", ephemeral=True)
            except:
                pass
            return

        try:
            embed = combat.get_status_embed()
            embed.add_field(
                name="⚙️ Действие",
                value="Выберите вспомогательное действие:",
                inline=False
            )
        except Exception as e:
            logger.error(f"⚙️ actions_callback: ОШИБКА embed: {e}", exc_info=True)
            return

        try:
            await interaction.edit_original_response(embed=embed, view=view)
        except Exception as e:
            logger.error(f"⚙️ actions_callback: ОШИБКА edit: {e}", exc_info=True)

    async def grenade_single_callback(self, interaction: discord.Interaction):
        if not await self._check_turn(interaction):
            return
        combat = combat_manager.get_combat(self.user_id)
        actor = combat.get_current_actor()
        if actor.get_shell_ammo_count() <= 0:
            await interaction.response.send_message("❌ ГП-25 не заряжен!", ephemeral=True)
            return
        if not await safe_defer(interaction):
            return
        embed, view = await handle_combat_action(interaction, "grenade_single")
        if embed is None:
            return
        try:
            await interaction.edit_original_response(embed=embed, view=view)
        except Exception as e:
            logger.error(f"Ошибка grenade_single: {e}")

    async def grenade_group_callback(self, interaction: discord.Interaction):
        if not await self._check_turn(interaction):
            return
        combat = combat_manager.get_combat(self.user_id)
        actor = combat.get_current_actor()
        if actor.get_shell_ammo_count() <= 0:
            await interaction.response.send_message("❌ ГП-25 не заряжен!", ephemeral=True)
            return
        if not await safe_defer(interaction):
            return
        embed, view = await handle_combat_action(interaction, "grenade_group")
        if embed is None:
            return
        try:
            await interaction.edit_original_response(embed=embed, view=view)
        except Exception as e:
            logger.error(f"Ошибка grenade_group: {e}")

    async def defend_callback(self, interaction: discord.Interaction):
        if not await self._check_turn(interaction):
            return

        self.action_type = None

        if not await safe_defer(interaction):
            return
        embed, view = await handle_combat_action(interaction, "defend")
        if embed is None:
            return
        try:
            await interaction.edit_original_response(embed=embed, view=view)
        except Exception as e:
            logger.error(f"Ошибка defend: {e}")

    async def finish_callback(self, interaction: discord.Interaction):
        if not await self._check_turn(interaction):
            return
        combat = combat_manager.get_combat(self.user_id)
        if not combat.enemy.can_finish():
            await interaction.response.send_message("❌ Нельзя добить!", ephemeral=True)
            return

        self.action_type = None

        if not await safe_defer(interaction):
            return
        embed, view = await handle_combat_action(interaction, "finish")
        if embed is None:
            return
        try:
            await interaction.edit_original_response(embed=embed, view=view)
        except Exception as e:
            logger.error(f"Ошибка finish: {e}")

    async def spare_callback(self, interaction: discord.Interaction):
        if not await self._check_turn(interaction):
            return
        combat = combat_manager.get_combat(self.user_id)
        if not combat.enemy.can_be_spared():
            await interaction.response.send_message("❌ Враг не сдался!", ephemeral=True)
            return

        self.action_type = None

        if not await safe_defer(interaction):
            return
        embed, view = await handle_combat_action(interaction, "spare")
        if embed is None:
            return
        try:
            await interaction.edit_original_response(embed=embed, view=view)
        except Exception as e:
            logger.error(f"Ошибка spare: {e}")