package httpapi

import (
	"net/http"

	"github.com/go-chi/chi/v5"
	"github.com/jackc/pgx/v5/pgxpool"

	"appartment/internal/listings"
)

// NewRouter wires up dependencies and returns an http.Handler you can serve.
func NewRouter(db *pgxpool.Pool) http.Handler {
	repo := listings.NewRepo(db)
	svc := listings.NewService(repo)
	h := NewHandler(svc)

	r := chi.NewRouter()
	r.Use(corsMiddleware)

	// Lightweight health check for uptime checks.
	r.Get("/health", func(w http.ResponseWriter, _ *http.Request) {
		w.Write([]byte("ok"))
	})

	// Data endpoints.
	r.Get("/blocks", h.ListBlocks)
	r.Get("/listings", h.ListListings)

	return r
}

// corsMiddleware allows the SPA (localhost:5173) to call the API during dev.
// Loosen for now; tighten origins/methods/headers as needed.
func corsMiddleware(next http.Handler) http.Handler {
	return http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		w.Header().Set("Access-Control-Allow-Origin", "*")
		w.Header().Set("Access-Control-Allow-Methods", "GET, OPTIONS")
		w.Header().Set("Access-Control-Allow-Headers", "Content-Type, Authorization")

		if r.Method == http.MethodOptions {
			w.WriteHeader(http.StatusNoContent)
			return
		}
		next.ServeHTTP(w, r)
	})
}
