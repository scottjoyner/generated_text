import express from 'express';
import path from 'path';
import dotenv from 'dotenv';

dotenv.config();
const __dirname = path.resolve();
const app = express();

const API_BASE = process.env.API_BASE || 'http://localhost:8000';
const PORT = process.env.PORT || 5173;

app.set('views', path.join(__dirname, 'src', 'pug'));
app.set('view engine', 'pug');

app.use('/public', express.static(path.join(__dirname, 'public')));

// Pass env to templates
app.use((req, res, next) => {
  res.locals.API_BASE = API_BASE;
  next();
});

app.get('/', (req, res) => res.redirect('/models'));

app.get('/models', (req, res) => {
  res.render('models', { title: 'Models' });
});

app.get('/models/:id', (req, res) => {
  res.render('model-detail', { title: req.params.id, modelId: req.params.id });
});

app.listen(PORT, () => {
  console.log(`UI listening on http://localhost:${PORT} (API_BASE=${API_BASE})`);
});
