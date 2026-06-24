idf_component_register(SRCS "DHT22.c" "main.c" "veml7700.c" "coap_server_example_main.c"
                       INCLUDE_DIRS "."
                       REQUIRES driver nvs_flash esp_event esp_netif esp_wifi ultrasonic esp_idf_lib_helpers esp_http_client mqtt coap
    
                       )
                       
