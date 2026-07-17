;; TCP JSON Lines transport for the Roseus worker.
;; This intentionally implements only the JSON subset used by the Python bridge.

(defconstant +mi-json-space+ 32)
(defconstant +mi-json-tab+ 9)
(defconstant +mi-json-lf+ 10)
(defconstant +mi-json-cr+ 13)
(defconstant +mi-json-quote+ 34)
(defconstant +mi-json-backslash+ 92)
(defconstant +mi-json-lbrace+ 123)
(defconstant +mi-json-rbrace+ 125)
(defconstant +mi-json-lbracket+ 91)
(defconstant +mi-json-rbracket+ 93)
(defconstant +mi-json-colon+ 58)
(defconstant +mi-json-comma+ 44)
(defconstant +mi-json-minus+ 45)
(defconstant +mi-json-plus+ 43)
(defconstant +mi-json-dot+ 46)

(defun mi-json-char (text pos)
  (if (>= pos (length text)) nil (elt text pos)))

(defun mi-json-space-char-p (c)
  (or (= c +mi-json-space+)
      (= c +mi-json-tab+)
      (= c +mi-json-lf+)
      (= c +mi-json-cr+)))

(defun mi-json-digit-p (c)
  (and c (<= 48 c) (<= c 57)))

(defun mi-json-number-char-p (c)
  (or (mi-json-digit-p c)
      (= c +mi-json-minus+)
      (= c +mi-json-plus+)
      (= c +mi-json-dot+)
      (= c 101)
      (= c 69)))

(defun mi-json-skip-space (text pos)
  (while (and (< pos (length text))
              (mi-json-space-char-p (mi-json-char text pos)))
    (setq pos (+ pos 1)))
  pos)

(defun mi-json-literal-at-p (text pos literal)
  (and (<= (+ pos (length literal)) (length text))
       (string= (subseq text pos (+ pos (length literal))) literal)))

(defun mi-json-keyword-for-key (key)
  (cond
    ((string= key "protocol_version") :protocol-version)
    ((string= key "type") :type)
    ((string= key "request_id") :request-id)
    ((string= key "command_id") :command-id)
    ((string= key "end_effector") :end-effector)
    ((string= key "dry_run") :dry-run)
    ((string= key "segments") :segments)
    ((string= key "kind") :kind)
    ((string= key "frame_id") :frame-id)
    ((string= key "translation_mm") :translation-mm)
    ((string= key "rotation_axis") :rotation-axis)
    ((string= key "rotation_angle_rad") :rotation-angle-rad)
    ((string= key "duration_ms") :duration-ms)
    (t key)))

(defun mi-json-key-name (key)
  (cond
    ((eq key :protocol-version) "protocol_version")
    ((eq key :type) "type")
    ((eq key :request-id) "request_id")
    ((eq key :worker-state) "worker_state")
    ((eq key :robot-ready) "robot_ready")
    ((eq key :collision-checker-ready) "collision_checker_ready")
    ((eq key :success) "success")
    ((eq key :code) "code")
    ((eq key :message) "message")
    ((eq key :completed-segments) "completed_segments")
    ((eq key :collision) "collision")
    ((eq key :collision-type) "collision_type")
    ((eq key :collision-pairs) "collision_pairs")
    ((eq key :current-segment) "current_segment")
    ((eq key :total-segments) "total_segments")
    ((eq key :phase) "phase")
    ((eq key :progress) "progress")
    (t (format nil "~A" key))))

(defun mi-json-parse-string (text pos)
  (let ((out (make-string-output-stream))
        (c nil))
    (setq pos (+ pos 1))
    (while (< pos (length text))
      (setq c (mi-json-char text pos))
      (cond
        ((= c +mi-json-quote+)
         (return-from mi-json-parse-string
           (list (get-output-stream-string out) (+ pos 1))))
        ((= c +mi-json-backslash+)
         (setq pos (+ pos 1))
         (setq c (mi-json-char text pos))
         (cond
           ((= c +mi-json-quote+) (princ "\"" out))
           ((= c +mi-json-backslash+) (princ "\\" out))
           ((= c 47) (princ "/" out))
           ((= c 98) (princ (coerce (list 8) string) out))
           ((= c 102) (princ (coerce (list 12) string) out))
           ((= c 110) (princ (coerce (list 10) string) out))
           ((= c 114) (princ (coerce (list 13) string) out))
           ((= c 116) (princ (coerce (list 9) string) out))
           (t (princ (subseq text pos (+ pos 1)) out))))
        (t
         (princ (subseq text pos (+ pos 1)) out)))
      (setq pos (+ pos 1)))
    (error "unterminated JSON string")))

(defun mi-json-parse-number (text pos)
  (let ((start pos))
    (while (and (< pos (length text))
                (mi-json-number-char-p (mi-json-char text pos)))
      (setq pos (+ pos 1)))
    (list (read-from-string (subseq text start pos)) pos)))

(defun mi-json-parse-array (text pos)
  (let ((items nil)
        (parsed nil))
    (setq pos (mi-json-skip-space text (+ pos 1)))
    (when (= (mi-json-char text pos) +mi-json-rbracket+)
      (return-from mi-json-parse-array (list nil (+ pos 1))))
    (while t
      (setq parsed (mi-json-parse-value text pos))
      (setq items (append items (list (car parsed))))
      (setq pos (mi-json-skip-space text (cadr parsed)))
      (cond
        ((= (mi-json-char text pos) +mi-json-comma+)
         (setq pos (mi-json-skip-space text (+ pos 1))))
        ((= (mi-json-char text pos) +mi-json-rbracket+)
         (return-from mi-json-parse-array (list items (+ pos 1))))
        (t
         (error "invalid JSON array"))))))

(defun mi-json-parse-object (text pos)
  (let ((plist nil)
        (key-result nil)
        (value-result nil)
        (key nil))
    (setq pos (mi-json-skip-space text (+ pos 1)))
    (when (= (mi-json-char text pos) +mi-json-rbrace+)
      (return-from mi-json-parse-object (list nil (+ pos 1))))
    (while t
      (setq key-result (mi-json-parse-string text pos))
      (setq key (mi-json-keyword-for-key (car key-result)))
      (setq pos (mi-json-skip-space text (cadr key-result)))
      (unless (= (mi-json-char text pos) +mi-json-colon+)
        (error "invalid JSON object"))
      (setq value-result (mi-json-parse-value text (mi-json-skip-space text (+ pos 1))))
      (setq plist (append plist (list key (car value-result))))
      (setq pos (mi-json-skip-space text (cadr value-result)))
      (cond
        ((= (mi-json-char text pos) +mi-json-comma+)
         (setq pos (mi-json-skip-space text (+ pos 1))))
        ((= (mi-json-char text pos) +mi-json-rbrace+)
         (return-from mi-json-parse-object (list plist (+ pos 1))))
        (t
         (error "invalid JSON object"))))))

(defun mi-json-parse-value (text pos)
  (setq pos (mi-json-skip-space text pos))
  (let ((c (mi-json-char text pos)))
    (cond
      ((= c +mi-json-quote+) (mi-json-parse-string text pos))
      ((= c +mi-json-lbrace+) (mi-json-parse-object text pos))
      ((= c +mi-json-lbracket+) (mi-json-parse-array text pos))
      ((mi-json-literal-at-p text pos "true") (list t (+ pos 4)))
      ((mi-json-literal-at-p text pos "false") (list nil (+ pos 5)))
      ((mi-json-literal-at-p text pos "null") (list nil (+ pos 4)))
      ((or (mi-json-digit-p c) (= c +mi-json-minus+)) (mi-json-parse-number text pos))
      (t (error "invalid JSON value")))))

(defun mi-json-decode (line)
  (car (mi-json-parse-value line 0)))

(defun mi-json-escape-string (value out-stream)
  (let ((i 0)
        (c nil))
    (princ "\"" out-stream)
    (while (< i (length value))
      (setq c (mi-json-char value i))
      (cond
        ((= c +mi-json-quote+) (princ "\\\"" out-stream))
        ((= c +mi-json-backslash+) (princ "\\\\" out-stream))
        (t (princ (subseq value i (+ i 1)) out-stream)))
      (setq i (+ i 1)))
    (princ "\"" out-stream)))

(defun mi-json-list-key-p (key)
  (or (eq key :collision-pairs)))

(defun mi-json-write-array (items out-stream)
  (let ((first t))
    (princ "[" out-stream)
    (dolist (item items)
      (unless first (princ "," out-stream))
      (setq first nil)
      (mi-json-write-value item out-stream))
    (princ "]" out-stream)))

(defun mi-json-write-value (value out-stream)
  (cond
    ((stringp value) (mi-json-escape-string value out-stream))
    ((numberp value) (princ value out-stream))
    ((eq value t) (princ "true" out-stream))
    ((null value) (princ "false" out-stream))
    ((listp value) (mi-json-write-array value out-stream))
    (t (mi-json-escape-string (format nil "~A" value) out-stream))))

(defun mi-json-encode-plist (plist)
  (let ((out-stream (make-string-output-stream))
        (first t)
        (key nil)
        (value nil))
    (princ "{" out-stream)
    (while plist
      (setq key (car plist))
      (setq value (cadr plist))
      (unless first (princ "," out-stream))
      (setq first nil)
      (mi-json-escape-string (mi-json-key-name key) out-stream)
      (princ ":" out-stream)
      (if (and (null value) (mi-json-list-key-p key))
          (mi-json-write-array nil out-stream)
        (mi-json-write-value value out-stream))
      (setq plist (cddr plist)))
    (princ "}" out-stream)
    (get-output-stream-string out-stream)))

(defun motion-instruction-json-vector3 (value)
  (cond
    ((vectorp value) value)
    ((listp value) (apply #'float-vector value))
    (t #f(0.0 0.0 0.0))))

(defun motion-instruction-normalize-segment (segment)
  (list :kind (mi-getf segment :kind "translation")
        :frame-id (mi-getf segment :frame-id "")
        :translation-mm
        (motion-instruction-json-vector3 (mi-getf segment :translation-mm '(0.0 0.0 0.0)))
        :rotation-axis
        (motion-instruction-json-vector3 (mi-getf segment :rotation-axis '(0.0 0.0 0.0)))
        :rotation-angle-rad (mi-getf segment :rotation-angle-rad 0.0)
        :duration-ms (mi-getf segment :duration-ms 5000)))

(defun motion-instruction-plist-remove (plist key)
  (let ((result nil))
    (while plist
      (unless (eq (car plist) key)
        (setq result (append result (list (car plist) (cadr plist)))))
      (setq plist (cddr plist)))
    result))

(defun motion-instruction-normalize-request (request)
  (let ((segments nil))
    (dolist (segment (mi-getf request :segments nil))
      (setq segments (append segments (list (motion-instruction-normalize-segment segment)))))
    (append (motion-instruction-plist-remove request :segments)
            (list :segments segments))))

(defun motion-instruction-collision-pair-string (pair)
  (cond
    ((stringp pair) pair)
    ((and (listp pair) (>= (length pair) 2))
     (format nil "~A:~A" (car pair) (cadr pair)))
    (t (format nil "~A" pair))))

(defun motion-instruction-result-message (request result)
  (let ((pairs nil))
    (dolist (pair (mi-getf result :collision-pairs nil))
      (setq pairs (append pairs (list (motion-instruction-collision-pair-string pair)))))
    (list :protocol-version "1.0"
          :type "result"
          :request-id (mi-getf request :request-id "")
          :success (mi-getf result :success nil)
          :code (mi-getf result :code "EXECUTION_FAILED")
          :message (mi-getf result :message "")
          :completed-segments (mi-getf result :completed-segments 0)
          :collision (mi-getf result :collision nil)
          :collision-type (mi-getf result :collision-type "none")
          :collision-pairs pairs)))

(defun motion-instruction-pong-message (request state)
  (list :protocol-version "1.0"
        :type "pong"
        :request-id (mi-getf request :request-id "")
        :worker-state "idle"
        :robot-ready (not (null (mi-getf state :robot nil)))
        :collision-checker-ready (not (null (mi-getf state :collision-check-fn nil)))))

(defun motion-instruction-feedback-message (request phase current total progress message)
  (list :protocol-version "1.0"
        :type "feedback"
        :request-id (mi-getf request :request-id "")
        :phase phase
        :current-segment current
        :total-segments total
        :progress progress
        :message message))

(defun motion-instruction-write-json-line (out-stream message)
  (format out-stream "~A~%" (mi-json-encode-plist message))
  (finish-output out-stream))

(defun motion-instruction-handle-execute-request (out-stream state request)
  (let* ((normalized-request (motion-instruction-normalize-request request))
         (segments (mi-getf normalized-request :segments nil))
         (result nil))
    (motion-instruction-write-json-line
     out-stream
     (motion-instruction-feedback-message
      normalized-request "preflight" 0 (length segments) 0.0 "preflight started"))
    (setq result
          (motion-instruction-execute-request
           (mi-getf state :robot nil)
           (mi-getf state :robot-interface nil)
           (append normalized-request
                   (list :end-effector-map (mi-getf state :end-effector-map nil)
                         :debug-view (mi-getf state :debug-view nil)))
           (mi-getf state :apply-translation-fn nil)
           (mi-getf state :apply-rotation-fn nil)
           (mi-getf state :collision-check-fn nil)
           (mi-getf state :execute-fn nil)
           (mi-getf state :wait-fn nil)
           (mi-getf state :collision-policy :required)))
    (motion-instruction-write-json-line
     out-stream
     (motion-instruction-result-message normalized-request result))))

(defun motion-instruction-handle-request-line (out-stream state line)
  (let ((request (mi-json-decode line)))
    (cond
      ((not (string= (mi-getf request :protocol-version "") "1.0"))
       (motion-instruction-write-json-line
        out-stream
        (motion-instruction-result-message
         request
         (mi-error "EXECUTOR_UNAVAILABLE" "protocol version mismatch"))))
      ((string= (mi-getf request :type "") "ping")
       (motion-instruction-write-json-line
        out-stream
        (motion-instruction-pong-message request state)))
      ((string= (mi-getf request :type "") "execute_motion")
       (motion-instruction-handle-execute-request out-stream state request))
      (t
       (motion-instruction-write-json-line
        out-stream
        (motion-instruction-result-message
         request
         (mi-error "REJECTED_INVALID" "unknown request type")))))))

(defun motion-instruction-serve-once (state host port)
  (let* ((sa (make-socket-address :domain af_inet :host host :port port))
         (sp (make-socket-port sa))
         (conn nil)
         (line nil))
    (unless (derivedp sp socket-port)
      (error "failed to create motion_instruction server socket"))
    (setq conn (make-server-socket-stream sp))
    (unwind-protect
      (progn
        (setq line (read-line conn nil nil))
        (when line
          (motion-instruction-handle-request-line conn state line)))
      (close conn)
      (unix::uclose (send sp :fd)))))

(defun motion-instruction-serve-forever (state host port)
  (let* ((sa (make-socket-address :domain af_inet :host host :port port))
         (sp (make-socket-port sa))
         (conn nil)
         (line nil))
    (unless (derivedp sp socket-port)
      (error "failed to create motion_instruction server socket"))
    (format t "motion_instruction Roseus worker listening on ~A:~A~%" host port)
    (while t
      (setq conn (make-server-socket-stream sp))
      (unwind-protect
        (progn
          (setq line (read-line conn nil nil))
          (when line
            (motion-instruction-handle-request-line conn state line)))
        (close conn)))))
