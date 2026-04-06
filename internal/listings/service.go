package listings

import "context"

// Service holds business logic; keeps handlers thin and testable.
type Service struct {
	repo *Repo
}

func NewService(r *Repo) *Service {
	return &Service{repo: r}
}

// List returns listings with filters applied.
func (s *Service) List(ctx context.Context, f Filters) ([]Listing, error) {
	return s.repo.List(ctx, f)
}

// ListBlocks currently returns a static list; later this can hit the DB.
func (s *Service) ListBlocks(_ context.Context) []map[string]string {
	return []map[string]string{
		{"code": "blok-67", "name": "Blok 67 (Belville / A Blok)", "city": "belgrade"},
		{"code": "blok-65", "name": "Blok 65", "city": "belgrade"},
		{"code": "blok-64", "name": "Blok 64", "city": "belgrade"},
		{"code": "blok-70", "name": "Blok 70", "city": "belgrade"},
		{"code": "blok-38", "name": "Blok 38", "city": "belgrade"},
		{"code": "blok-33", "name": "Blok 33 (Genex)", "city": "belgrade"},
		{"code": "pancevo", "name": "Pančevo", "city": "pancevo"},
	}
}

