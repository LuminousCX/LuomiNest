/**
 * LuomiNest P4 - 板级引脚集中定义
 * 任何引脚都从这一个文件查, 严禁在 bsp/ 其他文件直接写 GPIO_NUM_x
 * 详细分层约定见 D:\luominest\firmware\CLAUDE.md §7
 */

#ifndef BSP_PINS_H
#define BSP_PINS_H

#include "driver/gpio.h"

/* === LCD (JD9165, 1024x600 MIPI-DSI) === */
#define BSP_LCD_RST_PIN     GPIO_NUM_0
#define BSP_LCD_BL_PIN      GPIO_NUM_23   /* 背光 PWM, LEDC channel 1 */

/* MIPI DSI PHY 供电 (LDO 3, 2.5V) */
#define BSP_MIPI_PHY_LDO_CHAN        3
#define BSP_MIPI_PHY_LDO_VOLTAGE_MV  2500

/* === LCD 时序参数 (JD9165 数据手册) === */
#define BSP_LCD_H_RES        1024
#define BSP_LCD_V_RES        600
#define BSP_LCD_DSI_LANES    2
#define BSP_LCD_LANE_MBPS    750
#define BSP_LCD_DPI_CLK_MHZ  74   /* 量化→80MHz, vsync≈92Hz */

/* === Touch (GT911 I2C) === */
#define BSP_TOUCH_SDA_PIN    GPIO_NUM_7
#define BSP_TOUCH_SCL_PIN    GPIO_NUM_8
#define BSP_TOUCH_RST_PIN    GPIO_NUM_NC
#define BSP_TOUCH_INT_PIN    GPIO_NUM_NC

/* === SPI Master (P4 <-> C6 协处理器, 私有协议) ===
 * 引脚对应见 CLAUDE.md §6: CLK=GP2, MOSI=GP3, MISO=GP4, CS=GP21, HS=GP6
 * 40 MHz, MODE 0, HALFDUPLEX, P4 作 Master, C6 作 Slave
 * 这一版走 polling (切片 5 简单), 切片 8 切到 DMA + interrupt
 */
#define BSP_SPI_P4_CLK_PIN   GPIO_NUM_2
#define BSP_SPI_P4_MOSI_PIN  GPIO_NUM_3
#define BSP_SPI_P4_MISO_PIN  GPIO_NUM_4
#define BSP_SPI_P4_CS_PIN    GPIO_NUM_21
#define BSP_SPI_P4_HS_PIN    GPIO_NUM_6       /* C6 准备就绪握手, 上升沿触发 */
#define BSP_SPI_P4_FREQ_HZ   (40 * 1000 * 1000)
#define BSP_SPI_P4_HOST      SPI2_HOST        /* P4 上 SPI2/SPI3 可用, 选 SPI2 */

/* === SDMMC (SD 卡, 4-bit) === */
#define BSP_SDMMC_CLK_PIN    GPIO_NUM_43
#define BSP_SDMMC_CMD_PIN    GPIO_NUM_44
#define BSP_SDMMC_D0_PIN     GPIO_NUM_39
#define BSP_SDMMC_D1_PIN     GPIO_NUM_40
#define BSP_SDMMC_D2_PIN     GPIO_NUM_41
#define BSP_SDMMC_D3_PIN     GPIO_NUM_42
#define BSP_SD_LDO_CHAN       4

/* === Ethernet (IP101G RMII) === */
#define BSP_ETH_MDC_PIN      GPIO_NUM_31
#define BSP_ETH_MDIO_PIN     GPIO_NUM_52
#define BSP_ETH_PHY_RST_PIN  GPIO_NUM_51

#endif /* BSP_PINS_H */
