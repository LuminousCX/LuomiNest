"""
内置技能模块

包含系统内置的各种技能实现
"""

from app.runtime.plugin.skill.builtin.weather import get_weather, WEATHER_SKILL

__all__ = ['get_weather', 'WEATHER_SKILL']
