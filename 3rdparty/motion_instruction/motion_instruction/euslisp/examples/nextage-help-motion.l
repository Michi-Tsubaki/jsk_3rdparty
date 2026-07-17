(load "package://nextage_tutorials/euslisp/nextage-utils.l")
(load "package://motion_instruction/euslisp/motion-instruction.l")

(nextage-init)

(objects (list *nextage*))

(defun nextage-motion-instruction-collision-pair-name (pair)
  (list (send (car pair) :name)
        (send (cdr pair) :name)))

(defun nextage-motion-instruction-self-collision-check (robot context)
  (declare (ignore context))
  (let ((pairs (send robot :self-collision-check)))
    (if pairs
        (list :available t
              :collision t
              :category :self
              :pairs (mapcar #'nextage-motion-instruction-collision-pair-name pairs)
              :message "self collision detected")
      (motion-instruction-collision-ok))))

(help-motion *nextage* :robot-interface *ri* :collision-check-fn #'nextage-motion-instruction-self-collision-check)
(send *irtviewer* :draw-objects)
