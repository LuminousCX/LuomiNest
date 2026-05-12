#ifndef PIN_CONFIG_H
#define PIN_CONFIG_H

#include "driver/gpio.h"
#include "driver/spi_master.h"

#define ST7735S_SPI_HOST     SPI2_HOST
#define ST7735S_CLK_PIN      GPIO_NUM_12
#define ST7735S_MOSI_PIN     GPIO_NUM_11
#define ST7735S_DC_PIN       GPIO_NUM_5
#define ST7735S_RST_PIN      GPIO_NUM_4
#define ST7735S_CS_PIN       GPIO_NUM_10
#define ST7735S_BL_PIN       GPIO_NUM_6

#define ST7735S_WIDTH        128
#define ST7735S_HEIGHT       160
#define ST7735S_SPI_FREQ     20000000
#define ST7735S_X_OFFSET     0
#define ST7735S_Y_OFFSET     0
#define ST7735S_MADCTL       CONFIG_LN_ST7735S_MADCTL

#endif
