# Bindplane Self Monitoring
### Learn how to set up and ingest Bindplane self monitoring metrics to track collector health, pipeline anomalies and more. 

## 1. Adding Bindplane Collector as a Source

1. Navigate into your Configuration. On the left side, add a new Source.
   <img width="1702" height="1026" alt="image" src="https://github.com/user-attachments/assets/1a43df7d-9b2c-49dc-9f55-8262194d57c0" />


2. Select Bindplane Agent as the source type. Select both metrics and logs telemetry types then save the Source configuration. 
   <img width="1707" height="1196" alt="image" src="https://github.com/user-attachments/assets/d722c36f-ad23-4dbf-a757-5e38f805f0d0" />

## 2. Link Bindplane Agent Source to Dynatrace
  For both Logs and Metrics pipelines, click the + on the Bindplane agent source and link it to your Dynatrace destination.
  <img width="1599" height="1114" alt="image" src="https://github.com/user-attachments/assets/5ac6618f-f011-4ceb-bde6-030e858e93ea" />


## 3. Adding necessary Processor
    Bindplane self monitoring metrics are **cumulative data type**, but Dynatrace does not support this data type. In order to convert these to a Dynatrace supported data type, we need to add a processor to this stream. 

    1. Click on the processor to the right of the Bindplane Agent source. Then, click the Add Processor button. Select "Custom" processor. 
    <img width="46" height="144" alt="image" src="https://github.com/user-attachments/assets/36abaf54-bbdd-4950-9e14-4ccfe3d1b713" />

    2. In the Custom Processor, be sure to select both Metrics and Logs. Then in the Configuration box, add `cumulativetodelta: {} ` . 






