;; Generic default adapters. Robot-specific code should override these callbacks.

(defun motion-instruction-map-pair-value (pair)
  (if (listp (cdr pair))
      (cadr pair)
    (cdr pair)))

(defun motion-instruction-end-effector-map-lookup (end-effector end-effector-map)
  (dolist (pair end-effector-map)
    (when (and (consp pair)
               (or (eq (car pair) end-effector)
                   (and (stringp (car pair))
                        (stringp end-effector)
                        (string= (car pair) end-effector))))
      (return-from motion-instruction-end-effector-map-lookup
        (motion-instruction-map-pair-value pair))))
  nil)

(defun motion-instruction-default-end-effector-selector (end-effector)
  (cond
    ((symbolp end-effector) end-effector)
    ((not (stringp end-effector)) nil)
    ((or (string= end-effector "right_hand")
         (string= end-effector "right_tool")
         (string= end-effector "rarm")
         (string= end-effector ":rarm"))
     :rarm)
    ((or (string= end-effector "left_hand")
         (string= end-effector "left_tool")
         (string= end-effector "larm")
         (string= end-effector ":larm"))
     :larm)
    (t nil)))

(defun motion-instruction-end-effector-selector (end-effector context)
  (or (motion-instruction-end-effector-map-lookup
       end-effector
       (mi-getf context :end-effector-map nil))
      (motion-instruction-default-end-effector-selector end-effector)))

(defun motion-instruction-rotation-axis-keyword (rotation-axis)
  (let ((x (elt rotation-axis 0))
        (y (elt rotation-axis 1))
        (z (elt rotation-axis 2)))
    (cond
      ((not (= x 0.0)) :x)
      ((not (= y 0.0)) :y)
      ((not (= z 0.0)) :z)
      (t nil))))

(defun motion-instruction-rotation-axis-sign (rotation-axis)
  (let ((x (elt rotation-axis 0))
        (y (elt rotation-axis 1))
        (z (elt rotation-axis 2)))
    (cond
      ((not (= x 0.0)) (if (< x 0.0) -1.0 1.0))
      ((not (= y 0.0)) (if (< y 0.0) -1.0 1.0))
      ((not (= z 0.0)) (if (< z 0.0) -1.0 1.0))
      (t 1.0))))

(defun motion-instruction-rad2deg (angle-rad)
  (/ (* angle-rad 180.0) pi))

(defun motion-instruction-default-apply-translation
  (robot end-effector translation-mm frame-id context)
  (declare (ignore frame-id))
  (let ((selector (motion-instruction-end-effector-selector end-effector context))
        (result nil))
    (when (null selector)
      (return-from motion-instruction-default-apply-translation
        (mi-error "REJECTED_INVALID"
                  (format nil "unknown end-effector: ~A" end-effector))))
    (setq result (send robot selector :move-end-pos translation-mm))
    (if result
        (mi-ok)
      (mi-error "IK_FAILURE"
                (format nil "failed to solve IK for ~A translation" selector)))))

(defun motion-instruction-default-apply-rotation
  (robot end-effector rotation-axis rotation-angle-rad frame-id context)
  (declare (ignore frame-id))
  (let ((selector (motion-instruction-end-effector-selector end-effector context))
        (axis (motion-instruction-rotation-axis-keyword rotation-axis))
        (angle-deg (* (motion-instruction-rotation-axis-sign rotation-axis)
                      (motion-instruction-rad2deg rotation-angle-rad)))
        (result nil))
    (when (null selector)
      (return-from motion-instruction-default-apply-rotation
        (mi-error "REJECTED_INVALID"
                  (format nil "unknown end-effector: ~A" end-effector))))
    (when (null axis)
      (return-from motion-instruction-default-apply-rotation
        (mi-error "REJECTED_INVALID" "rotation axis is zero")))
    (setq result (send robot selector :move-end-rot angle-deg axis))
    (if result
        (mi-ok)
      (mi-error "IK_FAILURE"
                (format nil "failed to solve IK for ~A rotation" selector)))))

(defun motion-instruction-default-execute
  (robot robot-interface duration-ms context)
  (declare (ignore context))
  (if (null robot-interface)
      (mi-error "EXECUTION_FAILED" "robot-interface is not set")
    (progn
      (send robot-interface :angle-vector (send robot :angle-vector) duration-ms)
      (mi-ok))))

(defun motion-instruction-default-wait (robot robot-interface context)
  (declare (ignore robot context))
  (if (null robot-interface)
      (mi-ok)
    (progn
      ;; wait-interpolation is robot-interface dependent; override wait-fn if needed.
      (send robot-interface :wait-interpolation)
      (mi-ok))))
