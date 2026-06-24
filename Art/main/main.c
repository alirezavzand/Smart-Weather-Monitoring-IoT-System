#include "esp_event.h"
#include "esp_err.h"
#include "freertos/FreeRTOS.h"
#include "freertos/task.h"
#include "freertos/event_groups.h"
#include "driver/i2c.h"
#include "esp_log.h"
#include "esp_system.h"
#include "rom/ets_sys.h"
#include "nvs_flash.h"
#include "driver/gpio.h"
#include "sdkconfig.h"
#include "esp_mac.h"
#include "esp_netif.h"
#include <math.h>
#include "coap3/libcoap.h"


#include "esp_http_client.h"

#include "protocol_examples_common.h"
#include "esp_wifi.h"
#include "mqtt_client.h"

#include "veml7700.h"
#include "DHT22.h"
#include "ultrasonic.h"

#define I2C_MASTER_NUM I2C_NUM_0	//check
#define I2C_MASTER_FREQ_HZ 100000 	//check

#define TAG "simple_connect_example"

#define SDA_PIN GPIO_NUM_21
#define SCL_PIN GPIO_NUM_22

#define MAX_DISTANCE_CM 500 // 5m max

#define TRIGGER_GPIO 5
#define ECHO_GPIO 18

/**
 * Function prototypes
 */
void i2c_master_setup(void);
void task_veml7700_read(void *ignore);
void DHT_task(void *ignore);
void ultrasonic_test(void *ignore);
void post_http_task(void *ignore);
void mqtt_app_start(void);
void mqtt_event_handler(void *handler_args, esp_event_base_t base, int32_t event_id, void *event_data);
extern void coap_example_server(void *p);
char data[128];
float temperature;
float humidity;
float movement;
int threshold = 10;
volatile float lux_als, lux_white, fc_als, fc_white;
float distance;
char protocol[] = "http";
int sampling_rate = 2500;


esp_http_client_config_t config = {
    .url = "http://192.168.13.126:5000/update",
	.method = HTTP_METHOD_POST,  
};

esp_mqtt_client_config_t mqtt_cfg = {
    .broker.address.uri = "mqtt://192.168.13.126",  // <-- your broker IP or URL
};

esp_mqtt_client_handle_t client = NULL;


/**
 * @brief Standard application entry point.
 * 
 */
void app_main()
{
	ESP_ERROR_CHECK(nvs_flash_init());
	// Must call before wifi/http functions
	ESP_ERROR_CHECK(esp_netif_init());
	ESP_ERROR_CHECK(esp_event_loop_create_default());
	ESP_ERROR_CHECK(example_connect());

	client = esp_mqtt_client_init(&mqtt_cfg);

	// Subscribe to topic
	esp_mqtt_client_register_event(client, ESP_EVENT_ANY_ID, mqtt_event_handler, NULL);
	esp_mqtt_client_start(client);

	coap_startup();
	// Initialize I2C
	i2c_master_setup();
	
	xTaskCreate(ultrasonic_test, "ultrasonic_test", configMINIMAL_STACK_SIZE * 3, NULL, 10, NULL);
	xTaskCreate(DHT_task, "DHT_task", 2048, NULL, 5, NULL );
	xTaskCreate(task_veml7700_read, "task_read_veml7700",  4096, NULL, 6, NULL);
	xTaskCreate(post_http_task, "post_http_task",  4096, NULL, 6, NULL);

}

/**
 * @brief Configure the ESP host as an I2C master device.
 * 
 */
void i2c_master_setup(void)
{
	i2c_config_t conf;

	conf.mode = I2C_MODE_MASTER;
	conf.sda_io_num = SDA_PIN;
	conf.scl_io_num = SCL_PIN;
	conf.sda_pullup_en = GPIO_PULLUP_ENABLE;
	conf.scl_pullup_en = GPIO_PULLUP_ENABLE;
	conf.master.clk_speed = I2C_MASTER_FREQ_HZ;
	conf.clk_flags = 0;

	i2c_param_config(I2C_MASTER_NUM, &conf);
	i2c_driver_install(I2C_MASTER_NUM, I2C_MODE_MASTER, 0, 0, 0);
}

/**
 * @brief FreeRTOS-compatible task to periodically read and print sensor data.
 * 
 * @param ignore Ignore
 */
void task_veml7700_read(void *ignore)
{ 
	veml7700_handle_t veml7700_dev;

	esp_err_t init_result = veml7700_initialize(&veml7700_dev, I2C_MASTER_NUM);
	if (init_result != ESP_OK) {
		ESP_LOGE("VEML7700", "Failed to initialize. Result: %d\n", init_result);
		return;
	}

	ESP_LOGI("VEML7700", "Reading data...\r\n");

	while (true) {
		

		// Read the ALS data
		ESP_ERROR_CHECK( veml7700_read_als_lux_auto(veml7700_dev, &lux_als) );
		// Convert to foot candles
		fc_als = lux_als * LUX_FC_COEFFICIENT;

		// Read the White data
		ESP_ERROR_CHECK( veml7700_read_white_lux_auto(veml7700_dev, &lux_white) );
		// Convert to foot candles
		fc_white = lux_white * LUX_FC_COEFFICIENT;

		printf("VEML7700 measured ALS %0.4f lux or %0.4f fc \n", lux_als, fc_als);
		printf("VEML7700 measured White %0.4f lux or %0.4f fc \n\n", lux_white, fc_white);

		vTaskDelay(pdMS_TO_TICKS(sampling_rate));
	}

	vTaskDelete(NULL);
}

void DHT_task(void *pvParameter)
{
	setDHTgpio( 4 );
	printf( "Starting DHT Task\n\n");

	while(1) {
	
		printf("=== Reading DHT ===\n" );
		int ret = readDHT();
		
		errorHandler(ret);

		printf( "Hum %.1f\n", getHumidity() );
		printf( "Tmp %.1f\n", getTemperature() );
		
		temperature = getTemperature();
		humidity = getHumidity();
		// -- wait at least 2 sec before reading again ------------
		// The interval of whole process must be beyond 2 seconds !! 
		vTaskDelay(pdMS_TO_TICKS(sampling_rate));
	}
}

void ultrasonic_test(void *pvParameters)
{
    ultrasonic_sensor_t sensor = {
        .trigger_pin = TRIGGER_GPIO,
        .echo_pin = ECHO_GPIO
    };
	extern esp_mqtt_client_handle_t client;
	char detection[16];

    ultrasonic_init(&sensor);
	float prev_distance = 0;

    while (true)
    {
        //float distance;
        esp_err_t res = ultrasonic_measure(&sensor, MAX_DISTANCE_CM, &distance);
        if (res != ESP_OK)
        {
            printf("Error %d: ", res);
            switch (res)
            {
                case ESP_ERR_ULTRASONIC_PING:
                    printf("Cannot ping (device is in invalid state)\n");
                    break;
                case ESP_ERR_ULTRASONIC_PING_TIMEOUT:
                    printf("Ping timeout (no device found)\n");
                    break;
                case ESP_ERR_ULTRASONIC_ECHO_TIMEOUT:
                    printf("Echo timeout (i.e. distance too big)\n");
                    break;
                default:
                    printf("%s\n", esp_err_to_name(res));
            }
        }
        else
			distance = distance*100;
            printf("Distance: %0.04f cm\n", distance);
			movement = fabs(distance - prev_distance);
			if (movement>threshold){
				printf("movement detected\n");
				sprintf(detection, "%.2f", movement);
				esp_mqtt_client_publish(client, "esp32/movement", detection, 0, 1, 0);
			}


		prev_distance = distance;
        vTaskDelay(pdMS_TO_TICKS(500));
    }
}

void post_http_task(void *pvParameter){

	while(true){

	if (strcmp(protocol, "coap") == 0) {
		vTaskDelete(NULL);

	}
	snprintf(data, sizeof(data),
    	"{\"temp\": %.2f, \"hum\": %.2f, \"move\": %.2f,\"light\": %.2f}", temperature, humidity, distance, lux_als);
		 
	esp_http_client_handle_t client = esp_http_client_init(&config);

	esp_http_client_set_header(client, "Content-Type", "application/json");
    esp_http_client_set_post_field(client, data, strlen(data));
	esp_err_t err = esp_http_client_perform(client);
	vTaskDelay(pdMS_TO_TICKS(sampling_rate*1.01));

	}

}

void mqtt_event_handler(void *handler_args, esp_event_base_t base, int32_t event_id, void *event_data)
{
    esp_mqtt_event_handle_t event = event_data;
    esp_mqtt_client_handle_t client = event->client;
	
    switch (event_id) {
    case MQTT_EVENT_CONNECTED:
        printf("MQTT connected, subscribing...\n");
        esp_mqtt_client_subscribe(client, "esp32/protocol", 0);
		esp_mqtt_client_subscribe(client, "esp32/sampling_rate", 0);
		esp_mqtt_client_subscribe(client, "esp32/motion_alert", 0);
        break;

    case MQTT_EVENT_DATA:
        printf("Received topic: %.*s\n", event->topic_len, event->topic);
        printf("Received data: %.*s\n", event->data_len, event->data);
		int data=0;
		
    	if (strncmp(event->topic, "esp32/protocol", event->topic_len) == 0){
        	
			if(strncmp(event->data, "http", event->data_len) == 0) {

				strcpy(protocol, "http");
				xTaskCreate(post_http_task, "post_http_task",  4096, NULL, 6, NULL);
				printf("Protocol is changed to %s .\n", protocol);


			}
			else if(strncmp(event->data, "coap", event->data_len) == 0) {

				strcpy(protocol, "coap");
				xTaskCreate(coap_example_server, "coap", 8 * 1024, NULL, 8, NULL);
				printf("Protocol is changed to %s .\n", protocol);
			}
			else{
				printf("Invalid protocol.\n");
			}
		}
		else if(strncmp(event->topic, "esp32/sampling_rate", event->topic_len) == 0){

			data = atoi(event->data);

			if(1999<data  && data<3600000){
				sampling_rate = data;
				printf("sampling rate changed to %d.\n", sampling_rate);
			}
			else{
				printf("Invalid sampling rate!\n");
			}
		}
		else if(strncmp(event->topic, "esp32/motion_alert", event->topic_len) == 0){
			data = atoi(event->data);

			if(1<data && data<501){
				threshold = data;
				printf("motion threshold changed to %d.\n", threshold);
			}
			else{
				printf("Invalid motion threshold.\n");
			}
		}
        break;
    default:
        break;
    }
	
}



