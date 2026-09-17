func (r *EventSubscriptionReconciler) Reconcile(ctx context.Context, req ctrl.Request) (ctrl.Result, error) {
    // Fetch the EventSubscription instance
    var eventSubscription appsv1.EventSubscription
    if err := r.Get(ctx, req.NamespacedName, &eventSubscription); err != nil {
        return ctrl.Result{}, client.IgnoreNotFound(err)
    }

    // Add finalizer for cleanup
    if !controllerutil.ContainsFinalizer(&eventSubscription, "eventsubscription.finalizers.example.com") {
        controllerutil.AddFinalizer(&eventSubscription, "eventsubscription.finalizers.example.com")
        if err := r.Update(ctx, &eventSubscription); err != nil {
            return ctrl.Result{}, err
        }
    }

    // Handle deletion
    if !eventSubscription.ObjectMeta.DeletionTimestamp.IsZero() {
        // Unsubscribe logic
        if err := unsubscribeFromServer(eventSubscription.Spec.ServerUrl, eventSubscription.Spec.SubscriptionId); err != nil {
            return ctrl.Result{}, err
        }
        controllerutil.RemoveFinalizer(&eventSubscription, "eventsubscription.finalizers.example.com")
        if err := r.Update(ctx, &eventSubscription); err != nil {
            return ctrl.Result{}, err
        }

        // Delete corresponding EventHandling CRs
        var eventHandlingList appsv1.EventHandlingList
        if err := r.List(ctx, &eventHandlingList, client.MatchingFields{"spec.subscriptionId": eventSubscription.Spec.SubscriptionId}); err != nil {
            return ctrl.Result{}, err
        }
        for _, eventHandling := range eventHandlingList.Items {
            if err := r.Delete(ctx, &eventHandling); err != nil {
                return ctrl.Result{}, err
            }
        }

        return ctrl.Result{}, nil
    }

    // Prepare the subscription request
    serverUrl := eventSubscription.Spec.ServerUrl
    requestBody := eventSubscription.Spec.RequestBody

    // Example HTTP POST request to subscribe to events
    jsonData, err := json.Marshal(requestBody)
    if err != nil {
        return ctrl.Result{}, err
    }

    resp, err := http.Post(serverUrl, "application/json", bytes.NewBuffer(jsonData))
    if err != nil {
        return ctrl.Result{}, err
    }
    defer resp.Body.Close()

    // Update status based on subscription result
    eventSubscription.Status.Subscribed = (resp.StatusCode == http.StatusOK)

    // Update the status of the EventSubscription resource
    if err := r.Status().Update(ctx, &eventSubscription); err != nil {
        return ctrl.Result{}, err
    }

    // Requeue if necessary
    if !eventSubscription.Status.Subscribed {
        return ctrl.Result{RequeueAfter: time.Minute * 5}, nil
    }

    return ctrl.Result{}, nil
}

// Function to unsubscribe from the server
func unsubscribeFromServer(serverUrl, subscriptionId string) error {
    // Construct the URL for the unsubscribe request
    unsubscribeUrl := fmt.Sprintf("%s/%s", serverUrl, subscriptionId)

    // Create the HTTP DELETE request
    req, err := http.NewRequest(http.MethodDelete, unsubscribeUrl, nil)
    if err != nil {
        return err
    }

    // Send the HTTP DELETE request
    client := &http.Client{}
    resp, err := client.Do(req)
    if err != nil {
        return err
    }
    defer resp.Body.Close()

    // Check the response status code
    if resp.StatusCode != http.StatusOK {
        return fmt.Errorf("failed to unsubscribe: status code %d", resp.StatusCode)
    }

    return nil
}