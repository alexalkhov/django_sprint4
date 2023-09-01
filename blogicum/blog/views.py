from django.conf import settings
from django.contrib.auth import get_user_model
from django.contrib.auth.mixins import LoginRequiredMixin
from django.db.models import Count
from django.shortcuts import get_object_or_404, redirect
from django.urls import reverse
from django.views.generic import (CreateView, DeleteView, DetailView, ListView,
                                  UpdateView)

from .forms import CommentForm, PostForm, ProfileUpdateForm
from .models import Category, Comment, Post
from django.core.exceptions import PermissionDenied
from django.http import Http404


User = get_user_model()


class ListMixin(ListView):
    model = Post
    paginate_by = settings.POSTS_ON_PAGE


class IndexListView(ListMixin):
    template_name = 'blog/index.html'

    def get_queryset(self):
        post_list = (
            Post
            .published
            .order_by('-pub_date')
            .annotate(comment_count=Count('comment'))
        )
        return post_list


class CategoryPostsView(ListMixin):
    template_name = 'blog/category.html'

    def get_queryset(self):
        self.category = get_object_or_404(
            Category,
            is_published=True,
            slug=self.kwargs['category_slug'],
        )
        self.post_list = (
            self.category
            .posts(manager='objects')
            .published()
            .order_by('-pub_date')
            ).annotate(comment_count=Count('comment'))
        return self.post_list

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['category'] = self.category
        return context


class PostDetailView(LoginRequiredMixin, DetailView):
    template_name = 'blog/detail.html'
    model = Post

    def get_queryset(self):
        post = get_object_or_404(Post, pk=self.kwargs['pk'])
        if (not post.is_published and (post.author != self.request.user)):
            raise Http404
        return super().get_queryset()

    def get_context_data(self, **kwargs):
        post = self.object
        context = super().get_context_data(**kwargs)
        if post is not None:
            context['comments'] = post.comment.select_related('author')
        context['form'] = CommentForm()
        return context


class PostViewMixin(LoginRequiredMixin):
    form_class = PostForm
    model = Post
    template_name = 'blog/create.html'


class PostCreateView(PostViewMixin, CreateView):
    def form_valid(self, form):
        form.instance.author = self.request.user
        return super().form_valid(form)

    def get_success_url(self):
        return reverse('blog:profile', args=[self.request.user.username])


class DispatchMixin():
    def dispatch(self, request, *args, **kwargs):
        self.post_id = kwargs['pk']
        if self.get_object().author != request.user:
            return redirect('blog:post_detail', pk=self.post_id)
        return super().dispatch(request, *args, **kwargs)


class PostUpdateView(PostViewMixin, DispatchMixin, UpdateView):
    def get_success_url(self):
        return reverse('blog:post_detail',
                       kwargs={'pk': self.post_id})


class PostDeleteView(PostViewMixin, DispatchMixin, DeleteView):
    def get_success_url(self):
        return reverse('blog:profile', args=[self.request.user.username])


class CommentMixin(LoginRequiredMixin):
    template_name = 'blog/comment.html'
    model = Comment
    form_class = CommentForm


class CommentCreateView(CommentMixin, CreateView):
    def form_valid(self, form):
        comment = get_object_or_404(Post, pk=self.kwargs['pk'])
        form.instance.author = self.request.user
        form.instance.post = comment
        return super().form_valid(form)

    def get_success_url(self):
        return reverse('blog:post_detail',
                       kwargs={'pk': self.kwargs['pk']})


class CommentChangeMixin:
    def get_object(self):
        comment_pk = self.kwargs['comment_pk']
        return get_object_or_404(Comment, pk=comment_pk)

    def get_success_url(self):
        return reverse('blog:post_detail', kwargs={'pk': self.object.post.pk})

    def dispatch(self, request, *args, **kwargs):
        comment = self.get_object()
        if comment.author != request.user and not request.user.is_superuser:
            raise PermissionDenied
        return super().dispatch(request, *args, **kwargs)


class CommentUpdateView(CommentChangeMixin, CommentMixin, UpdateView):
    pass


class CommentDeleteView(CommentChangeMixin, CommentMixin, DeleteView):
    pass


class ProfileListView(ListMixin):
    template_name = 'blog/profile.html'
    ordering = '-pub_date'

    def get_queryset(self):
        self.user = get_object_or_404(
            User,
            username=self.kwargs['username']
        )
        return (self.model.objects.select_related('author')
                .filter(author=self.user)
                .annotate(comment_count=Count('comment'))
                .order_by('-pub_date'))

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['profile'] = self.user
        return context


class ProfileUpdateView(LoginRequiredMixin, UpdateView):
    template_name = 'blog/user.html'
    form_class = ProfileUpdateForm

    def get_object(self):
        return self.request.user

    def get_success_url(self):
        return reverse('blog:profile', args=[self.request.user])
