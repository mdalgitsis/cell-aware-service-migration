func (r *StaticTableReconciler) Reconcile(ctx context.Context, req ctrl.Request) (ctrl.Result, error) {
    // Fetch the StaticTable instance
    var staticTable appsv1.StaticTable
    if err := r.Get(ctx, req.NamespacedName, &staticTable); err != nil {
        return ctrl.Result{}, client.IgnoreNotFound(err)
    }

    // Validate the mappings
    valid := true
    gnbIdSet := make(map[int]bool)
    for _, mapping := range staticTable.Spec.Mappings {
        if _, exists := gnbIdSet[mapping.GnbId]; exists {
            valid = false
            break
        }
        gnbIdSet[mapping.GnbId] = true
    }

    // Update status based on validation
    staticTable.Status.Valid = valid

    // Update the status of the StaticTable resource
    if err := r.Status().Update(ctx, &staticTable); err != nil {
        return ctrl.Result{}, err
    }

    // Requeue if necessary
    if !valid {
        return ctrl.Result{RequeueAfter: time.Minute * 5}, nil
    }

    return ctrl.Result{}, nil
}