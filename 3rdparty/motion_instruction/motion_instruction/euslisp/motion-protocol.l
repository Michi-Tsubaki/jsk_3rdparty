;; Minimal plist protocol helpers used by the generic worker core.

(defun mi-getf (plist key &optional default)
  (cond
    ((null plist) default)
    ((eq (car plist) key) (cadr plist))
    (t (mi-getf (cddr plist) key default))))

(defun mi-ok (&optional message)
  (list :success t :code "OK" :message (or message "")))

(defun mi-error (code message &optional collision collision-type collision-pairs completed-segments)
  (list :success nil
        :code code
        :message message
        :collision (or collision nil)
        :collision-type (or collision-type "none")
        :collision-pairs (or collision-pairs nil)
        :completed-segments (or completed-segments 0)))

(defun mi-kind (segment)
  (mi-getf segment :kind "translation"))

(defun mi-duration-ms (segment)
  (mi-getf segment :duration-ms 5000))
