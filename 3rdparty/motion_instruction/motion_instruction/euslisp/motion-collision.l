;; Collision callback contract helpers.

(defun motion-instruction-collision-ok ()
  (list :available t :collision nil :category :none :pairs nil :message ""))

(defun motion-instruction-collision-unavailable ()
  (list :available nil :collision nil :category :unknown :pairs nil
        :message "collision checker unavailable"))

(defun motion-instruction-collision-result->error (result)
  (let ((category (mi-getf result :category :unknown))
        (pairs (mi-getf result :pairs nil))
        (message (mi-getf result :message "collision detected")))
    (cond
      ((eq category :self)
       (mi-error "COLLISION_SELF" message t "self" pairs 0))
      ((eq category :static-environment)
       (mi-error "COLLISION_STATIC_ENVIRONMENT" message t "static_environment" pairs 0))
      ((eq category :dynamic-environment)
       (mi-error "COLLISION_DYNAMIC_ENVIRONMENT" message t "dynamic_environment" pairs 0))
      (t
       (mi-error "COLLISION_UNKNOWN" message t "unknown" pairs 0)))))
