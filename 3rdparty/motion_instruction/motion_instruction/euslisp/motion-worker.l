(defvar *motion-instruction-worker-state* nil)

(defun motion-instruction-debug-view-draw (context)
  (when (and (mi-getf context :debug-view nil)
             (boundp '*irtviewer*)
             *irtviewer*)
    (send *irtviewer* :draw-objects)))

(defun motion-instruction-debug-view-setup (robot context)
  (when (mi-getf context :debug-view nil)
    (when (fboundp 'objects)
      (objects (list robot)))
    (motion-instruction-debug-view-draw context)))

(defun motion-instruction-copy-angle-vector (robot)
  (copy-object (send robot :angle-vector)))

(defun motion-instruction-restore-angle-vector (robot angle-vector &optional context)
  (send robot :angle-vector angle-vector)
  (motion-instruction-debug-view-draw context)
  (mi-ok))

(defun motion-instruction-apply-segment
  (robot segment apply-translation-fn apply-rotation-fn context)
  (let ((kind (mi-kind segment)))
    (cond
      ((string= kind "translation")
       (funcall apply-translation-fn
                robot
                (mi-getf context :end-effector "")
                (mi-getf segment :translation-mm #f(0.0 0.0 0.0))
                (mi-getf segment :frame-id "")
                context))
      ((string= kind "rotation")
       (funcall apply-rotation-fn
                robot
                (mi-getf context :end-effector "")
                (mi-getf segment :rotation-axis #f(0.0 0.0 0.0))
                (mi-getf segment :rotation-angle-rad 0.0)
                (mi-getf segment :frame-id "")
                context))
      (t
       (mi-error "REJECTED_INVALID" "unknown segment kind")))))

(defun motion-instruction-check-collision (robot collision-check-fn collision-policy context)
  (cond
    ((null collision-check-fn)
     (if (eq collision-policy :required)
         (mi-error "EXECUTION_FAILED" "collision checker is required")
       (mi-ok "collision checker unavailable")))
    (t
     (let ((result (funcall collision-check-fn robot context)))
       (cond
         ((and (eq collision-policy :required)
               (not (mi-getf result :available nil)))
          (mi-error "EXECUTION_FAILED" "collision checker unavailable"))
         ((mi-getf result :collision nil)
          (motion-instruction-collision-result->error result))
         (t
          (mi-ok)))))))

(defun motion-instruction-preflight
  (robot segments apply-translation-fn apply-rotation-fn collision-check-fn collision-policy context)
  (let ((initial-angle-vector (motion-instruction-copy-angle-vector robot))
        (plan nil)
        (index 0)
        (result nil))
    (dolist (segment segments)
      (setq index (+ index 1))
      (setq result
            (motion-instruction-apply-segment
             robot segment apply-translation-fn apply-rotation-fn
             (append context (list :current-segment index))))
      (when (not (mi-getf result :success nil))
        (motion-instruction-restore-angle-vector robot initial-angle-vector context)
        (return-from motion-instruction-preflight result))
      (motion-instruction-debug-view-draw context)
      (setq result
            (motion-instruction-check-collision
             robot collision-check-fn collision-policy
             (append context (list :current-segment index))))
      (when (not (mi-getf result :success nil))
        (motion-instruction-restore-angle-vector robot initial-angle-vector context)
        (return-from motion-instruction-preflight result))
      (setq plan
            (append plan
                    (list (list :angle-vector (motion-instruction-copy-angle-vector robot)
                                :duration-ms (mi-duration-ms segment))))))
    (motion-instruction-restore-angle-vector robot initial-angle-vector context)
    (list :success t :code "OK" :message "preflight succeeded" :plan plan)))

(defun motion-instruction-execute-plan
  (robot robot-interface plan execute-fn wait-fn context)
  (let ((completed 0)
        (result nil))
    (dolist (step plan)
      (send robot :angle-vector (mi-getf step :angle-vector))
      (motion-instruction-debug-view-draw context)
      (setq result
            (funcall execute-fn
                     robot
                     robot-interface
                     (mi-getf step :duration-ms 5000)
                     (append context (list :completed-segments completed))))
      (when (not (mi-getf result :success nil))
        (return-from motion-instruction-execute-plan
          (mi-error "EXECUTION_FAILED"
                    (mi-getf result :message "execution failed")
                    nil "none" nil completed)))
      (when wait-fn
        (setq result (funcall wait-fn robot robot-interface context))
        (when (not (mi-getf result :success nil))
          (return-from motion-instruction-execute-plan
            (mi-error "EXECUTION_FAILED"
                      (mi-getf result :message "wait failed")
                      nil "none" nil completed))))
      (setq completed (+ completed 1)))
    (list :success t
          :code "OK"
          :message "motion completed"
          :completed-segments completed
          :collision nil
          :collision-type "none"
          :collision-pairs nil)))

(defun motion-instruction-execute-request
  (robot robot-interface request apply-translation-fn apply-rotation-fn
         collision-check-fn execute-fn wait-fn collision-policy)
  (let* ((segments (mi-getf request :segments nil))
         (dry-run (mi-getf request :dry-run nil))
         (context (list :command-id (mi-getf request :command-id "")
                        :end-effector (mi-getf request :end-effector "")
                        :end-effector-map (mi-getf request :end-effector-map nil)
                        :debug-view (mi-getf request :debug-view nil)))
         (preflight (motion-instruction-preflight
                     robot segments apply-translation-fn apply-rotation-fn
                     collision-check-fn collision-policy context)))
    (if (not (mi-getf preflight :success nil))
        preflight
      (if dry-run
          (list :success t
                :code "OK"
                :message "dry-run preflight succeeded"
                :completed-segments 0
                :collision nil
                :collision-type "none"
                :collision-pairs nil)
        (motion-instruction-execute-plan
         robot robot-interface (mi-getf preflight :plan nil) execute-fn wait-fn context)))))

(defun help-motion
  (robot
   &key
   robot-interface
   (host "127.0.0.1")
   (port 50950)
   end-effector-map
   apply-translation-fn
   apply-rotation-fn
   collision-check-fn
   execute-fn
   wait-fn
   stop-fn
   (collision-policy :required)
   (debug-view nil)
   (start-server t))
  (declare (ignore stop-fn))
  (setq *motion-instruction-worker-state*
        (list :robot robot
              :robot-interface robot-interface
              :end-effector-map end-effector-map
              :debug-view debug-view
              :apply-translation-fn (or apply-translation-fn
                                        #'motion-instruction-default-apply-translation)
              :apply-rotation-fn (or apply-rotation-fn
                                     #'motion-instruction-default-apply-rotation)
              :collision-check-fn collision-check-fn
              :execute-fn (or execute-fn #'motion-instruction-default-execute)
              :wait-fn (or wait-fn #'motion-instruction-default-wait)
              :collision-policy collision-policy))
  (motion-instruction-debug-view-setup robot *motion-instruction-worker-state*)
  (format t "motion_instruction help-motion worker state initialized.~%")
  (if start-server
      (motion-instruction-serve-forever *motion-instruction-worker-state* host port)
    *motion-instruction-worker-state*))
