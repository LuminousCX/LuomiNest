#ifndef PIN_CONFIG_H
#define PIN_CONFIG_H

#include "driver/gpio.h"

#define ILI9486_RST_PIN    GPIO_NUM_5
#define ILI9486_CS_PIN     GPIO_NUM_6
#define ILI9486_RS_PIN     GPIO_NUM_7
#define ILI9486_WR_PIN     GPIO_NUM_1
#define ILI9486_RD_PIN     GPIO_NUM_2

#define ILI9486_D0_PIN     GPIO_NUM_21
#define ILI9486_D1_PIN     GPIO_NUM_46
#define ILI9486_D2_PIN     GPIO_NUM_18
#define ILI9486_D3_PIN     GPIO_NUM_17
#define ILI9486_D4_PIN     GPIO_NUM_19
#define ILI9486_D5_PIN     GPIO_NUM_20
#define ILI9486_D6_PIN     GPIO_NUM_3
#define ILI9486_D7_PIN     GPIO_NUM_14

#define ILI9486_WIDTH      320
#define ILI9486_HEIGHT     480
#define ILI9486_MADCTL     0x00
#define ILI9486_PCLK_HZ    10000000

#define SD_SPI_HOST        SPI2_HOST
#define SD_SS_PIN          GPIO_NUM_10
#define SD_MOSI_PIN        GPIO_NUM_11
#define SD_MISO_PIN        GPIO_NUM_13
#define SD_SCK_PIN         GPIO_NUM_12
#define SD_SPI_FREQ        20000000

#define SD_MOUNT_POINT     "/sdcard"
#define FRAMES_BASE_PATH   "/sdcard/frames"

#endif
