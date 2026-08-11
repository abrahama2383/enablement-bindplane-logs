
## Extracting Metrics from Logs

Now that we've got our credential leak under control, leadership is asking for an assessment of the overall impact.  Let's figure out how many keys were exposed, and which ones.

Let's use Bindplane to create a metric for us. 

### 1. Parse the Credential Key

We're going to want to find out how many different sets of credentials were leaked, and how often.
Let's add a processor to the same node we used to redact the sensitive information.

1. Click "Add Processor".  Make sure to add the new processor after the Redaction one.  Processors are executed from top to bottom and we want to parse the redacted value, not the original one.
2. Find the Processor named "Parse with Regex" and select it.
3. Create a name for the new Proccesor
4. Beacuse we have already routed the logs, we know that only the logs we are targeting will ever pass through this processor, so no need for a condition.
5. For "Target Field Type", select "Attribute".  This means we want to add a new attribute field as a peer to the log body, not modify the body itself.
6. Leave target field blank - this will allow us to name the field inside of our regular expression (useful for parsing multiple fields at once)
7. Enter this regular expression: `BCH_ACCESS_KEY_ID=(?<bch_access_key_id>\w+)` it will match the key name and then capture the next string of word characters (`\w+`) after the equals sign. Whatever we place between `<` and `>` will become the attribute name.

You should see that the regular expression matches the key name.  Click "Save" and you'll see a preview of the extracted field on the right.

![Parse Regex](img/8-metric-extraction/1-parse-regex.png)

Save the changes to your processor and then rollout your changes to the agent.

### 2. Create a Metric

To create a metric from logs, we'll use a "Signal to Metric" connector.

In the output of the processor we just created, click on the pencil icon, create a connector, and then choose "Signal to Metric"

![Create Connector](img/8-metric-extraction/2-create-connector.gif)

Once the dialog for the connector opens, edit the configuration:

1. Create the Metric Name `log.exposed_bch_credentials.count`
2. Select "Sum" for the Metric Type and leave the value as 1.  This will count 1 for every occurrence of our log.
3. Add the attribute from our log for the key that we masked `bch_access_key_id`.  This will add a dimension to the metric that we can split or summarize by.
4. Click "Save" to create it.

![Signal to Metrics](img/8-metric-extraction/2-signal-to-metrics-connector.png)


### Metrics Pipeline

Once your connector is created, you'll notice the layout of your pipeline has changed, and your connector doesn't sit exactly between the processor and the output.

![New Connector](img/8-metric-extraction/3-added-signal-to-metrics.png)

This is beacuse we are now emitting a new telemetry type, Metrics, from our pipeline.  At this point, Bindplane will automatically route the Metrics coming out the this connector into our **Metrics Pipeline**.

The Metrics Pipeline is just below the logs piplin in the UI. Scroll down and expand it by clicking on the chevron.  

**Rollout the changes** and you'll see that the new Metric we created is flowing through this pipeline and to our Dynatrace destination.

![Metrics Pipeline](img/8-metric-extraction/3-metrics-pipeline.png)


### Exploring and Using Metrics

Now let's head over to Dynatrace to explore the new Metric.

1. Create a new [Notebook](https://docs.dynatrace.com/docs/analyze-explore-automate/dashboards-and-notebooks/notebooks) where you'll be able to run some queries.
2. Create a new Section of DQL type.

DQL has a command named [`metrics`](https://docs.dynatrace.com/docs/platform/grail/dynatrace-query-language/commands/metric-commands#metrics) that allows you to explore the presence and structure of the metrics, rather than charting or calculating them.

Use the following query to see if the metric you created is being ingested:
```
metrics | filter matchesPhrase(metric.key, "bch")
```
The results should show a permutation of that metric key for each of the exposed credential attribute values.

![Metric Keys](img/8-metric-extraction/4-metric-key-query.png)

Now let's do something useful with that data.  We want to find out how many sets of credentials were exposed. For that, we can use the [`timeseries`](https://docs.dynatrace.com/docs/platform/grail/dynatrace-query-language/commands/metric-commands#timeseries) command, which will return a series of values for the metric key we specify.

Write a DQL query that will show how many sets of credentials are exposed.

??? Hint "Timeseries Summarization"
    The straightforward way to use a timeseries is simply to plot the a line chart for each series split with the `by:` paramter:
    ```
    timeseries total = sum(log.exposed_bch_credentials.count), by: {bch_access_key_id}
    ``` 
    But with DQL, we can summarize even further - say, if we wanted to see a *total* of all of the values within the query timeframe:
    ```
    timeseries ts = sum(log.exposed_bch_credentials.count), by: {bch_access_key_id}
        | fieldsAdd total = arraySum(ts)
    ```

Run your query and inspect the results.

![Timeseries](img/8-metric-extraction/4-timeseries-query.png)

Now we can hash all of our credentials securely offline, and compare them to the values here to see which ones have been leaked!

<div class="grid cards" markdown>
- [Bindplane Health:octicons-arrow-right-24:](9-bindplane-health.md)
</div>