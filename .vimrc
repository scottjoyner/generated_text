" Set encoding
set encoding=utf-8

" Enable line numbers
set number

" Enable relative line numbers
set relativenumber

" Enable syntax highlighting
syntax on

" Enable file type detection
filetype plugin indent on

" Set tab and indentation options
set tabstop=4       " Number of spaces that a <Tab> counts for
set shiftwidth=4    " Number of spaces to use for each step of (auto)indent
set expandtab       " Use spaces instead of tabs
set autoindent      " Copy indent from current line when starting a new line
set smartindent     " Smart autoindenting on new lines

" Enable mouse support
set mouse=a         " Enable mouse usage (all modes)

" Set search options
set ignorecase      " Ignore case when searching
set smartcase       " Override 'ignorecase' if search pattern contains uppercase letters
set incsearch       " Show search matches as you type
set hlsearch        " Highlight search matches

" Set the color scheme
colorscheme desert  " Change to your preferred color scheme

" Enable line wrapping
set wrap            " Enable line wrapping
set linebreak       " Wrap lines at convenient points

" Show the matching part of the pair for [] {} and ()
set showmatch

" Enable clipboard access
set clipboard=unnamedplus

" Enable auto-completion
set completeopt=menuone,noinsert,noselect
set shortmess+=c

" Display the cursor position
set ruler

" Always show the status line
set laststatus=2

" Enable persistent undo
set undofile

" Enable folding
set foldmethod=syntax
set foldlevelstart=99

" Customize the status line
set statusline=%f\ %h%m%r%=%-14.(%l,%c%V%)\ %P

" Set wild menu options
set wildmenu
set wildmode=list:longest

" Disable swap files
set noswapfile

" Configure backups and undo
set backup
set backupdir=~/.vim/backup//
set directory=~/.vim/swap//
set undodir=~/.vim/undo//

" Enable syntax-based code folding
set foldmethod=syntax

" Set up mappings for convenience
nnoremap <C-s> :w<CR>        " Save file with Ctrl-s
nnoremap <C-q> :q<CR>        " Quit with Ctrl-q
inoremap jk <Esc>            " Exit insert mode with jk

" Configure plugins (assuming using vim-plug for plugin management)
call plug#begin('~/.vim/plugged')

" Example plugins
Plug 'tpope/vim-sensible'
Plug 'scrooloose/nerdtree'
Plug 'itchyny/lightline.vim'
Plug 'junegunn/fzf', { 'do': { -> fzf#install() } }
Plug 'junegunn/fzf.vim'
Plug 'airblade/vim-gitgutter'
Plug 'jiangmiao/auto-pairs'
Plug 'preservim/nerdcommenter'
Plug 'sheerun/vim-polyglot'
Plug 'tpope/vim-fugitive'

call plug#end()

" NERDTree settings
map <C-n> :NERDTreeToggle<CR>
autocmd vimenter * NERDTree

" GitGutter settings
set updatetime=100

" FZF settings
set rtp+=~/.fzf

" Additional configurations and mappings can be added here
