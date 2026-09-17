func (r *EventHandlingReconciler) Reconcile(ctx context.Context, req ctrl.Request) (ctrl.Result, error) {
    // Fetch the EventHandling instance
    var eventHandling appsv1.EventHandling
    if err := r.Get(ctx, req.NamespacedName, &eventHandling); err != nil {
        return ctrl.Result{}, client.IgnoreNotFound(err)
    }

    // Example event data structure
    type EventData struct {
        SupiId string `json:"supiId"`
        GnbId  int    `json:"gnbId"`
    }

    // Extract SUPI ID and gNB ID from event data
    var eventData EventData
    if err := json.Unmarshal(eventBody, &eventData); err != nil {
        return ctrl.Result{}, err
    }
    supiId := eventData.SupiId
    gnbId := eventData.GnbId

    // Check if the event matches the SUPI ID in the EventHandling spec
    if eventHandling.Spec.SupiId != supiId {
        return ctrl.Result{}, nil // Ignore events not related to this SUPI ID
    }

    // Lookup siteId from StaticTable using tableId
    var staticTableList appsv1.StaticTableList
    if err := r.List(ctx, &staticTableList, client.MatchingFields{"spec.tableId": eventHandling.Spec.TableId}); err != nil {
        return ctrl.Result{}, err
    }

    siteId := ""
    for _, staticTable := range staticTableList.Items {
        for _, mapping := range staticTable.Spec.Mappings {
            if mapping.GnbId == gnbId {
                siteId = mapping.SiteId
                break
            }
        }
    }

    // Update the EventHandling CR with the event data
    eventHandling.Status.GnbId = gnbId
    eventHandling.Status.SiteId = siteId
    if err := r.Status().Update(ctx, &eventHandling); err != nil {
        return ctrl.Result{}, err
    }

    return ctrl.Result{}, nil
}