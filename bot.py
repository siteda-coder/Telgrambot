"""
Simple Network Bot for R1 and R2
Run: python bot.py
"""

import os
import logging
from datetime import datetime
from pathlib import Path

from netmiko import ConnectHandler
from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes

# ── Config ────────────────────────────────────────
TELEGRAM_TOKEN = "8374622558:AAGPqB0lh7cS9Y8pXa7RyZyHkD2a8gBSXcs"

DEVICES = {
    "R1": {
        "device_type": "cisco_ios",
        "host": "192.168.1.150",
        "username": "admin",
        "password": "admin",
        "secret": "admin",
    },
    "R2": {
        "device_type": "cisco_ios",
        "host": "192.168.1.151",
        "username": "admin",
        "password": "admin",
        "secret": "admin",
    },
}

BACKUP_DIR = Path("backups")
BACKUP_DIR.mkdir(exist_ok=True)

logging.basicConfig(level=logging.INFO)

# ── SSH Helper ────────────────────────────────────

def run_command(device_name: str, command: str) -> str:
    """SSH into device and run a command."""
    if device_name.upper() not in DEVICES:
        return f"Device '{device_name}' not found. Use R1 or R2."
    try:
        conn = ConnectHandler(**DEVICES[device_name.upper()])
        conn.enable()
        output = conn.send_command(command)
        conn.disconnect()
        return output
    except Exception as e:
        return f"Error: {str(e)}"


def run_all(command: str) -> dict:
    """Run command on both R1 and R2."""
    results = {}
    for name in DEVICES:
        results[name] = run_command(name, command)
    return results


def push_config(device_name: str, commands: list) -> str:
    """Push config commands to a device."""
    if device_name.upper() not in DEVICES:
        return f"Device '{device_name}' not found."
    try:
        conn = ConnectHandler(**DEVICES[device_name.upper()])
        conn.enable()
        output = conn.send_config_set(commands)
        conn.disconnect()
        return output
    except Exception as e:
        return f"Error: {str(e)}"


# ── Reply Helper ──────────────────────────────────

async def reply(update: Update, text: str):
    """Send reply, splitting if too long."""
    text = str(text)
    for i in range(0, len(text), 4000):
        await update.message.reply_text(f"```\n{text[i:i+4000]}\n```", parse_mode="Markdown")


# ── Bot Commands ──────────────────────────────────

async def start(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    msg = (
        "🌐 *Network Bot — R1 & R2*\n\n"
        "/help — show all commands\n"
        "/devices — list devices\n"
        "/show <R1|R2|ALL> <command>\n"
        "/interfaces <R1|R2|ALL>\n"
        "/route <R1|R2|ALL>\n"
        "/ospf <R1|R2|ALL>\n"
        "/ping <device> <ip>\n"
        "/backup <R1|R2|ALL>\n"
        "/desc <device> <intf> <text>\n"
        "/shutdown <device> <intf>\n"
        "/noshutdown <device> <intf>\n"
    )
    await update.message.reply_text(msg, parse_mode="Markdown")


async def help_cmd(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    await start(update, ctx)


async def devices(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    msg = "📦 *Devices:*\n"
    for name, d in DEVICES.items():
        msg += f"• *{name}* → `{d['host']}`\n"
    await update.message.reply_text(msg, parse_mode="Markdown")


async def show(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    """/show R1 ip route"""
    if len(ctx.args) < 2:
        await update.message.reply_text("Usage: `/show <R1|R2|ALL> <command>`", parse_mode="Markdown")
        return
    device = ctx.args[0]
    command = "show " + " ".join(ctx.args[1:])
    await update.message.reply_text(f"⏳ Running on {device}...")

    if device.upper() == "ALL":
        results = run_all(command)
        for host, out in results.items():
            await reply(update, f"--- {host} ---\n{out}")
    else:
        out = run_command(device, command)
        await reply(update, f"--- {device.upper()} ---\n{out}")


async def interfaces(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    device = ctx.args[0] if ctx.args else "ALL"
    await update.message.reply_text(f"⏳ Getting interfaces on {device}...")
    if device.upper() == "ALL":
        for host, out in run_all("show ip interface brief").items():
            await reply(update, f"--- {host} ---\n{out}")
    else:
        out = run_command(device, "show ip interface brief")
        await reply(update, f"--- {device.upper()} ---\n{out}")


async def route(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    device = ctx.args[0] if ctx.args else "ALL"
    await update.message.reply_text(f"⏳ Getting routes on {device}...")
    if device.upper() == "ALL":
        for host, out in run_all("show ip route").items():
            await reply(update, f"--- {host} ---\n{out}")
    else:
        out = run_command(device, "show ip route")
        await reply(update, f"--- {device.upper()} ---\n{out}")


async def ospf(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    device = ctx.args[0] if ctx.args else "ALL"
    await update.message.reply_text(f"⏳ Getting OSPF neighbors on {device}...")
    if device.upper() == "ALL":
        for host, out in run_all("show ip ospf neighbor").items():
            await reply(update, f"--- {host} ---\n{out}")
    else:
        out = run_command(device, "show ip ospf neighbor")
        await reply(update, f"--- {device.upper()} ---\n{out}")


async def ping_cmd(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    """/ping R1 10.0.12.2"""
    if len(ctx.args) < 2:
        await update.message.reply_text("Usage: `/ping <device> <ip>`", parse_mode="Markdown")
        return
    device, target = ctx.args[0], ctx.args[1]
    await update.message.reply_text(f"🏓 Pinging {target} from {device}...")
    out = run_command(device, f"ping {target} repeat 5")
    await reply(update, out)


async def backup(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    device = ctx.args[0] if ctx.args else "ALL"
    targets = list(DEVICES.keys()) if device.upper() == "ALL" else [device.upper()]
    await update.message.reply_text(f"💾 Backing up {device}...")

    results = []
    for name in targets:
        out = run_command(name, "show running-config")
        if "Error" in out:
            results.append(f"❌ {name}: {out}")
        else:
            ts = datetime.now().strftime("%Y%m%d_%H%M%S")
            fname = BACKUP_DIR / f"{name}_{ts}.cfg"
            fname.write_text(out)
            results.append(f"✅ {name}: saved as {fname.name}")

    await update.message.reply_text("\n".join(results))


async def desc(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    """/desc R1 Gi0/1 TO-R2"""
    if len(ctx.args) < 3:
        await update.message.reply_text("Usage: `/desc <device> <interface> <description>`", parse_mode="Markdown")
        return
    device, intf = ctx.args[0], ctx.args[1]
    description = " ".join(ctx.args[2:])
    out = push_config(device, [f"interface {intf}", f" description {description}", "exit"])
    await reply(update, f"✅ {device} {intf}:\n{out}")


async def shutdown_cmd(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    """/shutdown R1 Gi0/1"""
    if len(ctx.args) < 2:
        await update.message.reply_text("Usage: `/shutdown <device> <interface>`", parse_mode="Markdown")
        return
    device, intf = ctx.args[0], ctx.args[1]
    out = push_config(device, [f"interface {intf}", " shutdown", "exit"])
    await reply(update, f"⛔ {device} {intf} shutdown:\n{out}")


async def noshutdown_cmd(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    """/noshutdown R1 Gi0/1"""
    if len(ctx.args) < 2:
        await update.message.reply_text("Usage: `/noshutdown <device> <interface>`", parse_mode="Markdown")
        return
    device, intf = ctx.args[0], ctx.args[1]
    out = push_config(device, [f"interface {intf}", " no shutdown", "exit"])
    await reply(update, f"✅ {device} {intf} no shutdown:\n{out}")


# ── Main ──────────────────────────────────────────

def main():
    app = Application.builder().token(TELEGRAM_TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("help", help_cmd))
    app.add_handler(CommandHandler("devices", devices))
    app.add_handler(CommandHandler("show", show))
    app.add_handler(CommandHandler("interfaces", interfaces))
    app.add_handler(CommandHandler("route", route))
    app.add_handler(CommandHandler("ospf", ospf))
    app.add_handler(CommandHandler("ping", ping_cmd))
    app.add_handler(CommandHandler("backup", backup))
    app.add_handler(CommandHandler("desc", desc))
    app.add_handler(CommandHandler("shutdown", shutdown_cmd))
    app.add_handler(CommandHandler("noshutdown", noshutdown_cmd))

    print("✅ Bot is running... Press Ctrl+C to stop.")
    app.run_polling()


if __name__ == "__main__":
    main()